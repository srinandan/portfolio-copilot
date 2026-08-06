// Package main is the frontend runtime binary — it serves the built Vue SPA
// from a static directory and reverse-proxies /api/* and /health to the
// gateway Cloud Run service, attaching a Google-signed ID token so the
// gateway (deployed with --no-allow-unauthenticated) accepts the call.
//
// The frontend Cloud Run service runs under portfolio-copilot-frontend-sa,
// which is granted roles/run.invoker on portfolio-copilot-gateway by
// scripts/setup_cloudrun.sh. On Cloud Run this binary uses the instance
// metadata server (via google.golang.org/api/idtoken.NewTokenSource) to
// mint an audience-scoped ID token per request; on localhost against a
// plain-HTTP gateway (make -C gateway local) the auth step is skipped.
package main

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"path"
	"path/filepath"
	"strings"

	"golang.org/x/oauth2"
	"google.golang.org/api/idtoken"
)

func main() {
	if err := run(); err != nil {
		slog.Error("fatal", "error", err)
		os.Exit(1)
	}
}

func run() error {
	port := envDefault("PORT", "8080")
	staticDir := envDefault("STATIC_DIR", "/dist")
	gatewayURL := os.Getenv("GATEWAY_URL")

	apiHandler := newAPIHandler(gatewayURL)

	mux := http.NewServeMux()
	mux.Handle("/api/", apiHandler)
	mux.Handle("/health", apiHandler)
	mux.Handle("/", spaHandler(staticDir))

	slog.Info("frontend listening",
		"port", port,
		"static_dir", staticDir,
		"gateway_url", redact(gatewayURL),
	)
	return http.ListenAndServe(":"+port, mux)
}

func envDefault(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func redact(gatewayURL string) string {
	if gatewayURL == "" {
		return "(unset — /api and /health will 503)"
	}
	return gatewayURL
}

// newAPIHandler builds a reverse proxy to gatewayURL. If gatewayURL is unset,
// returns a stub that always 503s so a mis-deployed frontend fails loudly.
// If gatewayURL is HTTPS (Cloud Run) we attach an ID token; if it's HTTP
// (local dev against `make -C gateway local`) we forward without auth.
func newAPIHandler(gatewayURL string) http.Handler {
	if gatewayURL == "" {
		return http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
			http.Error(w, "gateway not configured (GATEWAY_URL unset)", http.StatusServiceUnavailable)
		})
	}
	proxy, err := newReverseProxy(gatewayURL)
	if err != nil {
		slog.Error("build gateway proxy — /api and /health will 503", "error", err)
		return http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
			http.Error(w, "gateway proxy init failed", http.StatusServiceUnavailable)
		})
	}
	return proxy
}

// newReverseProxy is separated from newAPIHandler so tests can drive it
// directly with an injected TokenSource.
func newReverseProxy(gatewayURL string) (http.Handler, error) {
	// Trim a trailing slash — Cloud Run's ID-token audience check compares
	// exact strings, and the URL from `gcloud run services describe --format
	// value(status.url)` never has one. Normalizing here lets an operator set
	// GATEWAY_URL with or without a slash without hitting a 401 mismatch.
	gatewayURL = strings.TrimRight(gatewayURL, "/")

	u, err := url.Parse(gatewayURL)
	if err != nil {
		return nil, fmt.Errorf("parse GATEWAY_URL %q: %w", gatewayURL, err)
	}
	if u.Scheme != "http" && u.Scheme != "https" {
		return nil, fmt.Errorf("GATEWAY_URL must be http(s), got scheme %q", u.Scheme)
	}

	var ts oauth2.TokenSource
	if u.Scheme == "https" {
		// idtoken.NewTokenSource uses the metadata server on Cloud Run to mint an
		// audience-scoped ID token, or a service-account key file if
		// GOOGLE_APPLICATION_CREDENTIALS points at one. User creds (gcloud auth
		// application-default login) can't mint ID tokens, so local runs against
		// an https Cloud Run gateway fail here — that's fine, local dev uses the
		// http localhost gateway.
		ts, err = idtoken.NewTokenSource(context.Background(), gatewayURL)
		if err != nil {
			return nil, fmt.Errorf("id-token source for %s: %w", gatewayURL, err)
		}
		// Warm-mint a token at startup so the operator sees any auth failure in
		// the boot logs, not a 401 later. This also validates that the compute
		// metadata server is reachable and roles/iam.serviceAccountTokenCreator /
		// run.invoker are in place.
		tok, err := ts.Token()
		if err != nil {
			return nil, fmt.Errorf("warm-mint id-token for audience %q: %w", gatewayURL, err)
		}
		slog.Info("id-token source ready",
			"audience", gatewayURL,
			"token_length", len(tok.AccessToken),
		)
	}

	return buildProxy(u, ts), nil
}

// buildProxy assembles the httputil.ReverseProxy with optional ID-token
// injection. Split out for tests, which pass a stub TokenSource.
func buildProxy(target *url.URL, ts oauth2.TokenSource) http.Handler {
	proxy := httputil.NewSingleHostReverseProxy(target)
	origDirector := proxy.Director
	proxy.Director = func(r *http.Request) {
		origDirector(r)
		// Cloud Run routes on the Host header; the reverse proxy default keeps
		// the incoming Host, which won't match the *.run.app hostname.
		r.Host = target.Host
		if ts == nil {
			return
		}
		tok, err := ts.Token()
		if err != nil {
			slog.WarnContext(r.Context(),
				"id-token fetch failed — request will likely 401",
				"error", err,
				"audience", target.String(),
			)
			return
		}
		r.Header.Set("Authorization", "Bearer "+tok.AccessToken)
	}
	// Log every non-2xx from the gateway with the fields that answer the
	// obvious "why is it 401?" questions: was Authorization attached, what
	// audience is the token minted for, and what does Cloud Run's own
	// WWW-Authenticate response header say ("Missing token" vs
	// "invalid_token"). Happy path is silent.
	proxy.Transport = &authDiagnosticTransport{
		base:     http.DefaultTransport,
		audience: target.String(),
	}
	proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
		slog.WarnContext(r.Context(), "gateway proxy error", "error", err, "path", r.URL.Path)
		http.Error(w, "upstream gateway error", http.StatusBadGateway)
	}
	return proxy
}

// authDiagnosticTransport wraps a round tripper to log outbound request /
// response context whenever the gateway returns >= 400. Silent on 2xx/3xx.
type authDiagnosticTransport struct {
	base     http.RoundTripper
	audience string
}

func (t *authDiagnosticTransport) RoundTrip(r *http.Request) (*http.Response, error) {
	authAttached := r.Header.Get("Authorization") != ""
	resp, err := t.base.RoundTrip(r)
	if err != nil {
		return resp, err
	}
	if resp.StatusCode >= 400 {
		slog.WarnContext(r.Context(),
			"gateway returned error status",
			"status", resp.StatusCode,
			"path", r.URL.Path,
			"host", r.Host,
			"authorization_attached", authAttached,
			"audience", t.audience,
			"www_authenticate", resp.Header.Get("Www-Authenticate"),
		)
	}
	return resp, err
}

// spaHandler serves files from dir with an index.html fallback for
// client-side routing (Vue Router history mode). Missing static asset paths
// (anything with a file extension) 404 normally so the browser doesn't try
// to eval index.html as JS.
func spaHandler(dir string) http.Handler {
	fs := http.FileServer(http.Dir(dir))
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		clean := filepath.Join(dir, filepath.Clean(r.URL.Path))
		if info, err := os.Stat(clean); err == nil && !info.IsDir() {
			fs.ServeHTTP(w, r)
			return
		}
		if strings.Contains(path.Base(r.URL.Path), ".") {
			http.NotFound(w, r)
			return
		}
		http.ServeFile(w, r, filepath.Join(dir, "index.html"))
	})
}
