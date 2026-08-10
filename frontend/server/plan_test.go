package main

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
)

func init() {
	gin.SetMode(gin.TestMode)
}

func newTestRouter(oc *OrchestratorClient) *gin.Engine {
	r := gin.New()
	r.POST("/api/plan", oc.HandlePlan)
	r.POST("/api/plan/resume", oc.HandlePlanResume)
	return r
}

func TestHandlePlan_MissingUserID_Returns400(t *testing.T) {
	oc := &OrchestratorClient{directURL: "http://not-used", httpClient: http.DefaultClient}
	r := newTestRouter(oc)

	req := httptest.NewRequest(http.MethodPost, "/api/plan", strings.NewReader(`{"message":"hi"}`))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d: %s", w.Code, w.Body.String())
	}
}

func TestHandlePlan_NoOrchestratorConfigured_Returns503(t *testing.T) {
	oc := &OrchestratorClient{httpClient: http.DefaultClient}
	r := newTestRouter(oc)

	req := httptest.NewRequest(http.MethodPost, "/api/plan",
		strings.NewReader(`{"user_id":"u1","message":"hi"}`))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusServiceUnavailable {
		t.Fatalf("expected 503, got %d: %s", w.Code, w.Body.String())
	}
	if !strings.Contains(w.Body.String(), "not configured") {
		t.Errorf("expected 'not configured' in error: %s", w.Body.String())
	}
}

func TestHandlePlan_DirectMode_ProxiesSSE(t *testing.T) {
	// Fake orchestrator that returns two SSE frames.
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/invoke" {
			t.Errorf("expected /v1/invoke, got %s", r.URL.Path)
		}
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(http.StatusOK)
		fmt.Fprintf(w, "data: {\"kind\":\"event1\"}\n\n")
		w.(http.Flusher).Flush()
		fmt.Fprintf(w, "data: {\"kind\":\"event2\"}\n\n")
		w.(http.Flusher).Flush()
	}))
	defer upstream.Close()

	oc := &OrchestratorClient{directURL: upstream.URL, httpClient: http.DefaultClient}
	r := newTestRouter(oc)

	req := httptest.NewRequest(http.MethodPost, "/api/plan",
		strings.NewReader(`{"user_id":"u1","message":"hi"}`))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	if ct := w.Header().Get("Content-Type"); !strings.HasPrefix(ct, "text/event-stream") {
		t.Errorf("expected text/event-stream content-type, got %q", ct)
	}
	body := w.Body.String()
	if !strings.Contains(body, `data: {"kind":"event1"}`) || !strings.Contains(body, `data: {"kind":"event2"}`) {
		t.Errorf("expected both SSE events in body, got:\n%s", body)
	}
}

func TestHandlePlan_DirectMode_UpstreamError_EmitsSSEError(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		io.WriteString(w, "orchestrator exploded")
	}))
	defer upstream.Close()

	oc := &OrchestratorClient{directURL: upstream.URL, httpClient: http.DefaultClient}
	r := newTestRouter(oc)

	req := httptest.NewRequest(http.MethodPost, "/api/plan",
		strings.NewReader(`{"user_id":"u1","message":"hi"}`))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if !strings.Contains(w.Body.String(), "event: error") {
		t.Errorf("expected SSE error frame, got:\n%s", w.Body.String())
	}
	if !strings.Contains(w.Body.String(), "orchestrator exploded") {
		t.Errorf("expected upstream body in error frame, got:\n%s", w.Body.String())
	}
}

// captureSlog swaps slog's default logger for one writing JSON into a buffer, so
// tests can assert what was logged and restores the prior default when the test
// ends. The buffer captures all levels; assertions filter by content.
func captureSlog(t *testing.T) *bytes.Buffer {
	t.Helper()
	buf := &bytes.Buffer{}
	prior := slog.Default()
	slog.SetDefault(slog.New(slog.NewJSONHandler(buf, &slog.HandlerOptions{Level: slog.LevelDebug})))
	t.Cleanup(func() { slog.SetDefault(prior) })
	return buf
}

func TestHandlePlan_DirectMode_UpstreamError_LogsAtError(t *testing.T) {
	// The wire-level SSE error was already going out; the missing piece was
	// server-side logging. This test guards that regression: any upstream
	// failure MUST log at ERROR with structured context so operators can find
	// it in Cloud Logging.
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
		io.WriteString(w, "IAM binding missing on Agent Registry")
	}))
	defer upstream.Close()

	logs := captureSlog(t)
	oc := &OrchestratorClient{directURL: upstream.URL, httpClient: http.DefaultClient}
	r := newTestRouter(oc)

	req := httptest.NewRequest(http.MethodPost, "/api/plan",
		strings.NewReader(`{"user_id":"u1","message":"hi"}`))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	out := logs.String()
	if !strings.Contains(out, `"level":"ERROR"`) {
		t.Errorf("expected ERROR-level log, got:\n%s", out)
	}
	if !strings.Contains(out, "orchestrator 401") {
		t.Errorf("expected orchestrator 401 message in log, got:\n%s", out)
	}
	if !strings.Contains(out, `"status":401`) {
		t.Errorf("expected structured status=401 in log, got:\n%s", out)
	}
	if !strings.Contains(out, `"user_id":"u1"`) {
		t.Errorf("expected structured user_id in log, got:\n%s", out)
	}
	if !strings.Contains(out, "IAM binding missing on Agent Registry") {
		t.Errorf("expected upstream body in log, got:\n%s", out)
	}
}

func TestHandlePlan_AgentEngineMode_UpstreamError_LogsAtError(t *testing.T) {
	// Same guarantee for the Agent Engine backend path — a 401 from the
	// :streamQuery endpoint (missing aiplatform.user, wrong project, etc.)
	// used to only reach the browser. Now it must also hit the gateway logs.
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
		io.WriteString(w, `{"error":{"code":401,"message":"missing aiplatform.user"}}`)
	}))
	defer upstream.Close()

	logs := captureSlog(t)
	oc := &OrchestratorClient{
		agentEngineID: "projects/123/locations/us-central1/reasoningEngines/eng-xyz",
		tokenSource:   func(context.Context) (string, error) { return "test-token", nil },
		httpClient: &http.Client{
			Transport: rewriteHostTransport{target: upstream.URL, base: http.DefaultTransport},
			Timeout:   5 * time.Second,
		},
	}
	r := newTestRouter(oc)

	req := httptest.NewRequest(http.MethodPost, "/api/plan",
		strings.NewReader(`{"user_id":"u1","message":"hi"}`))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	out := logs.String()
	if !strings.Contains(out, `"level":"ERROR"`) {
		t.Errorf("expected ERROR log, got:\n%s", out)
	}
	if !strings.Contains(out, `"mode":"agent_engine"`) {
		t.Errorf("expected mode=agent_engine in log, got:\n%s", out)
	}
	if !strings.Contains(out, `"engine_id":"projects/123/locations/us-central1/reasoningEngines/eng-xyz"`) {
		t.Errorf("expected engine_id in log, got:\n%s", out)
	}
	if !strings.Contains(out, "missing aiplatform.user") {
		t.Errorf("expected upstream body in log, got:\n%s", out)
	}
}

func TestHandlePlanResume_RequiresIDs(t *testing.T) {
	oc := &OrchestratorClient{directURL: "http://not-used", httpClient: http.DefaultClient}
	r := newTestRouter(oc)

	req := httptest.NewRequest(http.MethodPost, "/api/plan/resume",
		strings.NewReader(`{"user_id":"u1"}`))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d: %s", w.Code, w.Body.String())
	}
	if !strings.Contains(w.Body.String(), "invocation_id") {
		t.Errorf("expected invocation_id in error, got: %s", w.Body.String())
	}
}

func TestHandlePlanResume_DirectMode_ProxiesSSE(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/resume" {
			t.Errorf("expected /v1/resume, got %s", r.URL.Path)
		}
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(http.StatusOK)
		fmt.Fprintf(w, "data: {\"kind\":\"resumed\"}\n\n")
		w.(http.Flusher).Flush()
	}))
	defer upstream.Close()

	oc := &OrchestratorClient{directURL: upstream.URL, httpClient: http.DefaultClient}
	r := newTestRouter(oc)

	req := httptest.NewRequest(http.MethodPost, "/api/plan/resume",
		strings.NewReader(`{"user_id":"u1","session_id":"s","invocation_id":"i","interrupt_id":"int","payload":{"decision":"approve"}}`))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	if !strings.Contains(w.Body.String(), `"resumed"`) {
		t.Errorf("expected forwarded SSE, got:\n%s", w.Body.String())
	}
}

func TestHandlePlan_AgentEngineMode_WrapsStreamAsSSE(t *testing.T) {
	// Fake Agent Engine returns newline-delimited JSON objects. Gateway must re-wrap
	// each object as a single SSE data: frame.
	var gotAuth, gotBody string
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotAuth = r.Header.Get("Authorization")
		b, _ := io.ReadAll(r.Body)
		gotBody = string(b)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		fmt.Fprintf(w, "{\"event\":\"first\"}\n{\"event\":\"second\"}\n")
		w.(http.Flusher).Flush()
	}))
	defer upstream.Close()

	// Monkey-patch the URL construction by using an OrchestratorClient whose token source
	// is a stub and whose HTTP client rewrites the *-aiplatform.googleapis.com host to point at
	// our test server.
	oc := &OrchestratorClient{
		agentEngineID: "projects/123/locations/us-central1/reasoningEngines/eng-xyz",
		tokenSource:   func(context.Context) (string, error) { return "test-token", nil },
		httpClient: &http.Client{
			Transport: rewriteHostTransport{target: upstream.URL, base: http.DefaultTransport},
			Timeout:   5 * time.Second,
		},
	}
	r := newTestRouter(oc)

	req := httptest.NewRequest(http.MethodPost, "/api/plan",
		strings.NewReader(`{"user_id":"u1","message":"hi"}`))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	if !strings.Contains(gotAuth, "Bearer test-token") {
		t.Errorf("expected Bearer test-token, got %q", gotAuth)
	}
	if !strings.Contains(gotBody, `"class_method":"invoke"`) {
		t.Errorf("expected invoke envelope, got %s", gotBody)
	}
	body := w.Body.String()
	if !strings.Contains(body, `data: {"event":"first"}`) || !strings.Contains(body, `data: {"event":"second"}`) {
		t.Errorf("expected two SSE frames, got:\n%s", body)
	}
}

// rewriteHostTransport swaps the request URL to point at a test server, so
// Agent Engine mode can be exercised without hitting real GCP endpoints.
type rewriteHostTransport struct {
	target string
	base   http.RoundTripper
}

func (r rewriteHostTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	// Preserve the original path (":streamQuery" endpoint) but swap scheme+host.
	newURL := r.target + req.URL.Path
	if req.URL.RawQuery != "" {
		newURL += "?" + req.URL.RawQuery
	}
	newReq, err := http.NewRequestWithContext(req.Context(), req.Method, newURL, req.Body)
	if err != nil {
		return nil, err
	}
	newReq.Header = req.Header.Clone()
	return r.base.RoundTrip(newReq)
}

func TestAgentEngineRegion(t *testing.T) {
	tests := []struct {
		name    string
		input   string
		want    string
		wantErr bool
	}{
		{"typical", "projects/123/locations/us-central1/reasoningEngines/abc", "us-central1", false},
		{"other region", "projects/x/locations/europe-west4/reasoningEngines/y", "europe-west4", false},
		{"no locations segment", "projects/x/reasoningEngines/y", "", true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := agentEngineRegion(tt.input)
			if (err != nil) != tt.wantErr {
				t.Fatalf("err=%v, wantErr=%v", err, tt.wantErr)
			}
			if got != tt.want {
				t.Errorf("got %q, want %q", got, tt.want)
			}
		})
	}
}
