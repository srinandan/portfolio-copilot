package main

import (
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"golang.org/x/oauth2"
)

type stubTokenSource struct {
	token string
	err   error
}

func (s stubTokenSource) Token() (*oauth2.Token, error) {
	if s.err != nil {
		return nil, s.err
	}
	return &oauth2.Token{AccessToken: s.token}, nil
}

func TestBuildProxy_AttachesIDTokenAndOverridesHost(t *testing.T) {
	var (
		gotAuth string
		gotHost string
		gotPath string
	)
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotAuth = r.Header.Get("Authorization")
		gotHost = r.Host
		gotPath = r.URL.Path
		w.WriteHeader(http.StatusOK)
		io.WriteString(w, "ok")
	}))
	defer upstream.Close()

	target, err := url.Parse(upstream.URL)
	if err != nil {
		t.Fatalf("parse upstream: %v", err)
	}
	h := buildProxy(target, stubTokenSource{token: "tok-abc"})

	req := httptest.NewRequest(http.MethodGet, "http://frontend.local/api/holdings", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("proxy status = %d, want 200; body=%s", w.Code, w.Body.String())
	}
	if gotAuth != "Bearer tok-abc" {
		t.Errorf("Authorization = %q, want Bearer tok-abc", gotAuth)
	}
	if gotHost != target.Host {
		t.Errorf("Host = %q, want %q (target host)", gotHost, target.Host)
	}
	if gotPath != "/api/holdings" {
		t.Errorf("path = %q, want /api/holdings", gotPath)
	}
}

func TestBuildProxy_NoTokenSource_SkipsAuthHeader(t *testing.T) {
	var gotAuth string
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotAuth = r.Header.Get("Authorization")
		w.WriteHeader(http.StatusOK)
	}))
	defer upstream.Close()

	target, _ := url.Parse(upstream.URL)
	h := buildProxy(target, nil)

	req := httptest.NewRequest(http.MethodGet, "http://frontend.local/api/x", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("status = %d", w.Code)
	}
	if gotAuth != "" {
		t.Errorf("Authorization = %q, want empty (local http mode should not sign)", gotAuth)
	}
}

func TestBuildProxy_TokenSourceFails_ForwardsWithoutAuth(t *testing.T) {
	var gotAuth string
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotAuth = r.Header.Get("Authorization")
		w.WriteHeader(http.StatusUnauthorized)
	}))
	defer upstream.Close()

	target, _ := url.Parse(upstream.URL)
	h := buildProxy(target, stubTokenSource{err: io.ErrUnexpectedEOF})

	req := httptest.NewRequest(http.MethodGet, "http://frontend.local/api/x", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if gotAuth != "" {
		t.Errorf("Authorization = %q, want empty (token failed, no header attached)", gotAuth)
	}
	// The upstream returned 401, which is what a real gateway would do without a token.
	if w.Code != http.StatusUnauthorized {
		t.Errorf("upstream status forwarded incorrectly: got %d", w.Code)
	}
}

func TestBuildProxy_UpstreamDown_Returns502(t *testing.T) {
	// Point at a definitely-closed port.
	target, _ := url.Parse("http://127.0.0.1:1")
	h := buildProxy(target, nil)

	req := httptest.NewRequest(http.MethodGet, "http://frontend.local/api/x", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusBadGateway {
		t.Errorf("status = %d, want 502", w.Code)
	}
}

func TestBuildProxy_LogsUpstream4xx_ForwardsStatus(t *testing.T) {
	// Ensure the diagnostic transport we install to warn on gateway >=400 also
	// forwards status + WWW-Authenticate untouched to the SPA. Otherwise a
	// diagnostic wrap would mask the actual failure the browser needs to see.
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Www-Authenticate", `Bearer error="invalid_token"`)
		w.WriteHeader(http.StatusUnauthorized)
	}))
	defer upstream.Close()

	target, _ := url.Parse(upstream.URL)
	h := buildProxy(target, stubTokenSource{token: "tok"})

	req := httptest.NewRequest(http.MethodGet, "http://frontend.local/api/holdings", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusUnauthorized {
		t.Errorf("status = %d, want 401 (proxy must forward upstream 401)", w.Code)
	}
	if got := w.Header().Get("Www-Authenticate"); got == "" {
		t.Errorf("Www-Authenticate not forwarded; got empty (need it for browser to see the reason)")
	}
}

func TestNewAPIHandler_UnsetGatewayURL_Returns503(t *testing.T) {
	h := newAPIHandler("")

	req := httptest.NewRequest(http.MethodGet, "http://frontend.local/api/x", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusServiceUnavailable {
		t.Errorf("status = %d, want 503", w.Code)
	}
	if !strings.Contains(w.Body.String(), "GATEWAY_URL") {
		t.Errorf("body should mention GATEWAY_URL: %s", w.Body.String())
	}
}

func TestNewReverseProxy_HTTP_SkipsTokenSource(t *testing.T) {
	// HTTP scheme should build without hitting idtoken.NewTokenSource — good for local dev.
	_, err := newReverseProxy("http://localhost:8080")
	if err != nil {
		t.Fatalf("expected http URL to build proxy without token source, got: %v", err)
	}
}

func TestNewReverseProxy_BadURL(t *testing.T) {
	_, err := newReverseProxy("ftp://nope")
	if err == nil {
		t.Fatal("expected error for non-http(s) scheme")
	}
	if !strings.Contains(err.Error(), "scheme") {
		t.Errorf("error should mention scheme: %v", err)
	}
}

func TestBuildProxy_NormalizesTrailingSlashOnAudience(t *testing.T) {
	// If GATEWAY_URL has a trailing slash the reverse-proxy still must send
	// requests to a normal host with normal-looking paths (no // duplication),
	// and — the whole reason for the trim in newReverseProxy — the audience
	// used to mint ID tokens must match Cloud Run's exact-string comparison.
	// This test drives buildProxy against a target with no trailing slash
	// (as newReverseProxy would produce after trimming) and asserts the
	// outgoing request path is clean.
	var gotPath string
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotPath = r.URL.Path
		w.WriteHeader(http.StatusOK)
	}))
	defer upstream.Close()

	// newReverseProxy trims the trailing slash before parsing; simulate the
	// trimmed URL here.
	target, _ := url.Parse(upstream.URL)
	h := buildProxy(target, nil)

	req := httptest.NewRequest(http.MethodGet, "http://frontend.local/api/holdings", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("status = %d", w.Code)
	}
	if gotPath != "/api/holdings" {
		t.Errorf("path = %q, want /api/holdings (no // duplication)", gotPath)
	}
}

func TestSPAHandler_ServesStaticFile(t *testing.T) {
	dir := t.TempDir()
	must(t, os.WriteFile(filepath.Join(dir, "index.html"), []byte("<html>root</html>"), 0o644))
	must(t, os.WriteFile(filepath.Join(dir, "app.js"), []byte("console.log(1)"), 0o644))

	h := spaHandler(dir)

	req := httptest.NewRequest(http.MethodGet, "http://frontend/app.js", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", w.Code)
	}
	if !strings.Contains(w.Body.String(), "console.log(1)") {
		t.Errorf("body = %q, want the app.js contents", w.Body.String())
	}
}

func TestSPAHandler_FallbackToIndexForClientRoute(t *testing.T) {
	dir := t.TempDir()
	must(t, os.WriteFile(filepath.Join(dir, "index.html"), []byte("<html>spa-root</html>"), 0o644))

	h := spaHandler(dir)

	// A Vue Router history-mode route with no file extension → serve index.html.
	req := httptest.NewRequest(http.MethodGet, "http://frontend/portfolio/rebalance", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (index fallback)", w.Code)
	}
	if !strings.Contains(w.Body.String(), "spa-root") {
		t.Errorf("body = %q, want index.html contents", w.Body.String())
	}
}

func TestSPAHandler_MissingAssetReturns404(t *testing.T) {
	dir := t.TempDir()
	must(t, os.WriteFile(filepath.Join(dir, "index.html"), []byte("root"), 0o644))

	h := spaHandler(dir)

	// A missing static asset (has a file extension) must 404, not silently serve index.html —
	// otherwise the browser would try to eval index.html as JS/CSS.
	req := httptest.NewRequest(http.MethodGet, "http://frontend/missing.js", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusNotFound {
		t.Errorf("status = %d, want 404", w.Code)
	}
}

func must(t *testing.T, err error) {
	t.Helper()
	if err != nil {
		t.Fatalf("setup: %v", err)
	}
}
