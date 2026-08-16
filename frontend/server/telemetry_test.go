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
)

func TestInitTracing_DisabledIsNoopButPropagates(t *testing.T) {
	t.Setenv("OTEL_TRACES_ENABLED", "false")
	shutdown, err := InitTracing(context.Background())
	if err != nil {
		t.Fatalf("InitTracing returned error: %v", err)
	}
	if shutdown == nil {
		t.Fatal("InitTracing returned nil shutdown")
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
