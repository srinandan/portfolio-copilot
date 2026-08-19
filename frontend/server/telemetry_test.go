package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"slices"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
	"go.opentelemetry.io/contrib/instrumentation/github.com/gin-gonic/gin/otelgin"
	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/propagation"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/sdk/trace/tracetest"
	oteltrace "go.opentelemetry.io/otel/trace"
)

func TestInitTracing_DisabledIsNoopButPropagates(t *testing.T) {
	t.Setenv("OTEL_TRACES_ENABLED", "false")
	shutdown, replayTP, err := InitTracing(context.Background())
	if err != nil {
		t.Fatalf("InitTracing returned error: %v", err)
	}
	if shutdown == nil {
		t.Fatal("InitTracing returned nil shutdown")
	}
	if replayTP != nil {
		t.Error("expected nil replay provider when export is disabled")
	}
	if err := shutdown(context.Background()); err != nil {
		t.Errorf("noop shutdown returned error: %v", err)
	}
	// The W3C propagator must be installed even when span export is disabled, so
	// trace context still flows browser -> Go -> orchestrator.
	fields := otel.GetTextMapPropagator().Fields()
	if !slices.Contains(fields, "traceparent") {
		t.Errorf("expected 'traceparent' in propagator fields, got %v", fields)
	}
}

func TestOTLPExportConfigured(t *testing.T) {
	cases := []struct {
		name string
		env  map[string]string
		want bool
	}{
		{"none", map[string]string{}, false},
		{"general endpoint", map[string]string{"OTEL_EXPORTER_OTLP_ENDPOINT": "http://collector:4318"}, true},
		{"traces endpoint", map[string]string{"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://collector:4318/v1/traces"}, true},
		{"exporter selector", map[string]string{"OTEL_TRACES_EXPORTER": "otlp"}, true},
		{"exporter selector cased", map[string]string{"OTEL_TRACES_EXPORTER": "OTLP"}, true},
		{"exporter selector other", map[string]string{"OTEL_TRACES_EXPORTER": "console"}, false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			// Clear all OTLP-selecting vars, then set the case's.
			for _, k := range []string{"OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "OTEL_TRACES_EXPORTER"} {
				t.Setenv(k, "")
			}
			for k, v := range tc.env {
				t.Setenv(k, v)
			}
			if got := otlpExportConfigured(); got != tc.want {
				t.Errorf("otlpExportConfigured() = %v, want %v", got, tc.want)
			}
		})
	}
}

// TestReplaySpan_PreservesIDs is the core #313 guarantee: a browser span
// forwarded through the replay tracer is exported as a real span that keeps the
// SPA-supplied trace id, span id, and parent span id — so the server request
// span (parented to the browser client span via the propagated traceparent)
// attaches to a real parent instead of an orphan.
func TestReplaySpan_PreservesIDs(t *testing.T) {
	inmem := tracetest.NewInMemoryExporter()
	tp := sdktrace.NewTracerProvider(
		sdktrace.WithSyncer(inmem),
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
		sdktrace.WithIDGenerator(seededIDGenerator{}),
	)
	t.Cleanup(func() { _ = tp.Shutdown(context.Background()) })

	ti := &TelemetryIngest{projectID: "test-project", tracer: tp.Tracer("browser-spa")}
	r := gin.New()
	r.POST("/api/telemetry/v1/traces", ti.HandleIngestTraces)

	const traceID = "0af7651916cd43dd8448eb211c80319c"
	const parentID = "b7ad6b7169203331" // browser root (user-action) span
	const childID = "00f067aa0ba902b7"  // browser client span, child of the root
	body := `{"spans":[
		{"traceId":"` + traceID + `","spanId":"` + parentID + `","name":"planning_turn_triggered","kind":"internal","startTimeUnixMs":1000,"endTimeUnixMs":2000,"attributes":{"user_id":"demo_user"}},
		{"traceId":"` + traceID + `","spanId":"` + childID + `","parentSpanId":"` + parentID + `","name":"POST /api/plan","kind":"client","startTimeUnixMs":1100,"endTimeUnixMs":1400,"attributes":{"http.status_code":200}}
	]}`
	req := httptest.NewRequest(http.MethodPost, "/api/telemetry/v1/traces", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusAccepted {
		t.Fatalf("expected 202, got %d: %s", w.Code, w.Body.String())
	}

	spans := inmem.GetSpans()
	if len(spans) != 2 {
		t.Fatalf("expected 2 exported spans, got %d", len(spans))
	}
	byID := map[string]tracetest.SpanStub{}
	for _, s := range spans {
		if s.SpanContext.TraceID().String() != traceID {
			t.Errorf("span %q has trace id %s, want %s", s.Name, s.SpanContext.TraceID(), traceID)
		}
		byID[s.SpanContext.SpanID().String()] = s
	}

	root, ok := byID[parentID]
	if !ok {
		t.Fatalf("root span id %s not preserved; got ids %v", parentID, keysOf(byID))
	}
	if root.Parent.IsValid() {
		t.Errorf("root span should have no valid parent, got %s", root.Parent.SpanID())
	}
	if root.SpanKind != oteltrace.SpanKindInternal {
		t.Errorf("root span kind = %v, want internal", root.SpanKind)
	}

	child, ok := byID[childID]
	if !ok {
		t.Fatalf("child span id %s not preserved; got ids %v", childID, keysOf(byID))
	}
	if child.Parent.SpanID().String() != parentID {
		t.Errorf("child parent span id = %s, want %s", child.Parent.SpanID(), parentID)
	}
	if child.SpanKind != oteltrace.SpanKindClient {
		t.Errorf("child span kind = %v, want client", child.SpanKind)
	}
	// Timestamps come from the SPA (unix ms), not wall clock.
	if child.StartTime.UnixMilli() != 1100 || child.EndTime.UnixMilli() != 1400 {
		t.Errorf("child span timing = [%d,%d]ms, want [1100,1400]ms",
			child.StartTime.UnixMilli(), child.EndTime.UnixMilli())
	}
}

func keysOf(m map[string]tracetest.SpanStub) []string {
	ks := make([]string, 0, len(m))
	for k := range m {
		ks = append(ks, k)
	}
	return ks
}

func newIngestRouter() *gin.Engine {
	ti := &TelemetryIngest{projectID: "test-project"}
	r := gin.New()
	r.POST("/api/telemetry/v1/traces", ti.HandleIngestTraces)
	return r
}

func postIngest(body string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodPost, "/api/telemetry/v1/traces", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	newIngestRouter().ServeHTTP(w, req)
	return w
}

func TestHandleIngestTraces_AcceptsValidSpans(t *testing.T) {
	w := postIngest(`{"spans":[
		{"traceId":"0af7651916cd43dd8448eb211c80319c","spanId":"b7ad6b7169203331","name":"planning_turn_triggered","kind":"client","startTimeUnixMs":1000,"endTimeUnixMs":1500,"attributes":{"user_id":"demo_user"}}
	]}`)
	if w.Code != http.StatusAccepted {
		t.Fatalf("expected 202, got %d: %s", w.Code, w.Body.String())
	}
	var resp map[string]int
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("bad response json: %v", err)
	}
	if resp["accepted"] != 1 {
		t.Errorf("expected accepted=1, got %d", resp["accepted"])
	}
}

func TestHandleIngestTraces_SkipsMalformedSpans(t *testing.T) {
	// Invalid trace/span ids (wrong length / non-hex) are skipped, not fatal.
	w := postIngest(`{"spans":[
		{"traceId":"too-short","spanId":"b7ad6b7169203331","name":"x","kind":"client"},
		{"traceId":"0af7651916cd43dd8448eb211c80319c","spanId":"nothex-nothex000","name":"y","kind":"client"}
	]}`)
	if w.Code != http.StatusAccepted {
		t.Fatalf("expected 202, got %d", w.Code)
	}
	var resp map[string]int
	_ = json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["accepted"] != 0 {
		t.Errorf("expected accepted=0 for malformed spans, got %d", resp["accepted"])
	}
}

func TestHandleIngestTraces_BadJSONReturns400(t *testing.T) {
	w := postIngest(`{ not json`)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", w.Code)
	}
}

// TestHandlePlan_PropagatesTraceparentToOrchestrator is the end-to-end propagation
// check: an incoming browser `traceparent` on /api/plan must continue to the
// orchestrator under the same trace id (otelgin extracts it, otelhttp re-injects it).
func TestHandlePlan_PropagatesTraceparentToOrchestrator(t *testing.T) {
	// A real (unsampled-export) provider with AlwaysSample so a valid span context
	// exists for otelhttp to inject.
	tp := sdktrace.NewTracerProvider(sdktrace.WithSampler(sdktrace.AlwaysSample()))
	prevTP := otel.GetTracerProvider()
	prevProp := otel.GetTextMapPropagator()
	otel.SetTracerProvider(tp)
	otel.SetTextMapPropagator(propagation.TraceContext{})
	t.Cleanup(func() {
		otel.SetTracerProvider(prevTP)
		otel.SetTextMapPropagator(prevProp)
		_ = tp.Shutdown(context.Background())
	})

	const incomingTraceID = "0af7651916cd43dd8448eb211c80319c"
	var gotTraceparent string
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotTraceparent = r.Header.Get("traceparent")
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, "data: {}\n\n")
		w.(http.Flusher).Flush()
	}))
	defer upstream.Close()

	oc := &OrchestratorClient{
		directURL:  upstream.URL,
		httpClient: &http.Client{Transport: otelhttp.NewTransport(http.DefaultTransport)},
	}
	r := gin.New()
	r.Use(otelgin.Middleware("test-frontend"))
	r.POST("/api/plan", oc.HandlePlan)

	req := httptest.NewRequest(http.MethodPost, "/api/plan", strings.NewReader(`{"user_id":"u1","message":"hi"}`))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("traceparent", "00-"+incomingTraceID+"-b7ad6b7169203331-01")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if gotTraceparent == "" {
		t.Fatal("orchestrator did not receive a traceparent header")
	}
	if !strings.Contains(gotTraceparent, incomingTraceID) {
		t.Errorf("expected propagated trace id %s in %q", incomingTraceID, gotTraceparent)
	}
}

// TestInvokeAgentEngine_PropagatesTraceContextInBody covers the Vertex
// :streamQuery workaround: Vertex re-issues its own request to the container and
// drops the header traceparent, so the gateway also injects the W3C context into
// the request BODY (`trace_context`) — that is what lets the orchestrator continue
// the browser -> Go trace instead of a disconnected one.
func TestInvokeAgentEngine_PropagatesTraceContextInBody(t *testing.T) {
	tp := sdktrace.NewTracerProvider(sdktrace.WithSampler(sdktrace.AlwaysSample()))
	prevTP := otel.GetTracerProvider()
	prevProp := otel.GetTextMapPropagator()
	otel.SetTracerProvider(tp)
	otel.SetTextMapPropagator(propagation.TraceContext{})
	t.Cleanup(func() {
		otel.SetTracerProvider(prevTP)
		otel.SetTextMapPropagator(prevProp)
		_ = tp.Shutdown(context.Background())
	})

	var gotBody string
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b, _ := io.ReadAll(r.Body)
		gotBody = string(b)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, "{}\n")
	}))
	defer upstream.Close()

	oc := &OrchestratorClient{
		agentEngineID: "projects/123/locations/us-central1/reasoningEngines/eng-xyz",
		tokenSource:   func(context.Context) (string, error) { return "test-token", nil },
		httpClient:    &http.Client{Transport: rewriteHostTransport{target: upstream.URL, base: http.DefaultTransport}},
	}

	// An active span so there is a trace context to inject into the body.
	ctx, span := tp.Tracer("test").Start(context.Background(), "gateway-span")
	traceID := span.SpanContext().TraceID().String()
	defer span.End()

	body, _, err := oc.invokeAgentEngine(ctx, PlanRequest{UserID: "u1", Message: "hi"}, false)
	if err != nil {
		t.Fatalf("invokeAgentEngine: %v", err)
	}
	_, _ = io.Copy(io.Discard, body)
	_ = body.Close()

	if !strings.Contains(gotBody, `"trace_context"`) {
		t.Fatalf("expected trace_context in :streamQuery body, got %s", gotBody)
	}
	if !strings.Contains(gotBody, traceID) {
		t.Errorf("expected body trace_context to carry trace id %s, got %s", traceID, gotBody)
	}
}
