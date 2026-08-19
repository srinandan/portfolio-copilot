package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"regexp"
	"strings"
	"time"

	texporter "github.com/GoogleCloudPlatform/opentelemetry-operations-go/exporter/trace"
	"github.com/gin-gonic/gin"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	oteltrace "go.opentelemetry.io/otel/trace"
)

// serviceName is the OpenTelemetry service.name reported for this process. It is
// what the correlated spans group under in Cloud Trace.
func serviceName() string {
	if n := os.Getenv("OTEL_SERVICE_NAME"); n != "" {
		return n
	}
	return "portfolio-copilot-frontend"
}

// browserServiceName is the service.name stamped on spans replayed from the SPA
// (see HandleIngestTraces). A distinct name keeps browser-origin spans visually
// separable from the Go server's own spans in the trace view, while the
// preserved trace id still groups them into the same end-to-end trace.
func browserServiceName() string {
	return serviceName() + "-spa"
}

// resolveProjectID resolves the GCP project for trace export / log correlation,
// mirroring how the store client resolves it.
func resolveProjectID() string {
	for _, k := range []string{"GOOGLE_CLOUD_PROJECT", "PROJECT_ID", "FIRESTORE_PROJECT_ID"} {
		if v := os.Getenv(k); v != "" {
			return v
		}
	}
	return ""
}

// otlpExportConfigured reports whether spans should be exported over OTLP rather
// than through the native Cloud Trace exporter. It follows the OpenTelemetry
// conventions: an explicit OTLP endpoint (general or traces-specific), or
// OTEL_TRACES_EXPORTER=otlp, opts in. When none is set the Cloud Trace exporter
// stays the default, so existing deployments are unaffected.
func otlpExportConfigured() bool {
	if os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT") != "" {
		return true
	}
	if os.Getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") != "" {
		return true
	}
	return strings.EqualFold(os.Getenv("OTEL_TRACES_EXPORTER"), "otlp")
}

// tracingExportEnabled reports whether spans should be exported at all. Export is
// opt-out via OTEL_TRACES_ENABLED=false. Otherwise it is enabled when there is a
// destination: an OTLP endpoint (OTLP forwarding, #313) or a resolvable GCP
// project (native Cloud Trace). Trace-context PROPAGATION is always on regardless
// of this (see InitTracing).
func tracingExportEnabled() bool {
	if v := os.Getenv("OTEL_TRACES_ENABLED"); v == "false" || v == "0" {
		return false
	}
	return otlpExportConfigured() || resolveProjectID() != ""
}

// newSpanExporter builds the configured span exporter. It returns the exporter
// and a short label naming the transport ("otlp" or "cloudtrace") for logging.
// It is safe to call more than once — each call yields an independent exporter,
// so the request-span provider and the browser-replay provider each own theirs
// and can be shut down without racing on a shared client.
func newSpanExporter(ctx context.Context) (sdktrace.SpanExporter, string, error) {
	if otlpExportConfigured() {
		// otlptracehttp reads OTEL_EXPORTER_OTLP_* from the environment (endpoint,
		// headers, TLS). With only OTEL_TRACES_EXPORTER=otlp set it falls back to
		// the spec default endpoint (localhost:4318) — the standard OTLP contract.
		exp, err := otlptracehttp.New(ctx)
		if err != nil {
			return nil, "otlp", fmt.Errorf("otlp trace exporter init: %w", err)
		}
		return exp, "otlp", nil
	}
	exp, err := texporter.New(texporter.WithProjectID(resolveProjectID()))
	if err != nil {
		return nil, "cloudtrace", fmt.Errorf("cloud trace exporter init: %w", err)
	}
	return exp, "cloudtrace", nil
}

// buildResource assembles the OTel resource for a provider, degrading to a
// service-name-only resource if the full resource can't be built (e.g. a schema
// conflict) rather than dropping tracing entirely.
func buildResource(ctx context.Context, name string) *resource.Resource {
	res, err := resource.New(ctx,
		resource.WithAttributes(attribute.String("service.name", name)),
		resource.WithTelemetrySDK(),
	)
	if err != nil {
		return resource.NewSchemaless(attribute.String("service.name", name))
	}
	return res
}

// newReplayTracerProvider builds the provider used to re-emit browser spans as
// real spans. Its seeded ID generator preserves the SPA-supplied trace/span ids
// (so the server request span, already parented to the browser client span via
// the propagated traceparent, attaches to a real parent), and AlwaysSample means
// a replayed span is never dropped for lacking a sampled parent flag.
func newReplayTracerProvider(ctx context.Context, exp sdktrace.SpanExporter) *sdktrace.TracerProvider {
	return sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exp),
		sdktrace.WithResource(buildResource(ctx, browserServiceName())),
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
		sdktrace.WithIDGenerator(seededIDGenerator{}),
	)
}

// InitTracing installs the global W3C TraceContext propagator and, when export is
// enabled, a TracerProvider backed by the configured exporter (OTLP when an OTLP
// endpoint is configured, otherwise the Cloud Trace exporter). It returns a
// shutdown function that flushes pending spans and the browser-replay
// TracerProvider (nil when export is disabled) that HandleIngestTraces uses to
// re-emit SPA spans as real spans.
//
// The propagator is installed unconditionally so `traceparent` flows
// browser -> Go server -> orchestrator even when this process does not export
// spans (e.g. local dev with no project or OTLP endpoint). When export is
// disabled the returned shutdown is a no-op, the global provider stays the
// default no-op provider, and the replay provider is nil (browser spans fall
// back to trace-correlated logs).
func InitTracing(ctx context.Context) (func(context.Context) error, *sdktrace.TracerProvider, error) {
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))

	noop := func(context.Context) error { return nil }

	if !tracingExportEnabled() {
		slog.InfoContext(ctx, "OpenTelemetry span export disabled; trace-context propagation active",
			slog.String("service", serviceName()))
		return noop, nil, nil
	}

	exporter, kind, err := newSpanExporter(ctx)
	if err != nil {
		return noop, nil, err
	}

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(buildResource(ctx, serviceName())),
	)
	otel.SetTracerProvider(tp)

	// A second provider re-emits browser spans through an independent exporter of
	// the same transport. If it can't be built the request-span provider still
	// works; browser spans just stay on the log-correlation fallback.
	var replayTP *sdktrace.TracerProvider
	if replayExp, _, rerr := newSpanExporter(ctx); rerr != nil {
		slog.WarnContext(ctx, "browser span replay disabled; falling back to trace-correlated logs",
			slog.String("error", rerr.Error()))
	} else {
		replayTP = newReplayTracerProvider(ctx, replayExp)
	}

	shutdown := func(ctx context.Context) error {
		errs := []error{tp.Shutdown(ctx)}
		if replayTP != nil {
			errs = append(errs, replayTP.Shutdown(ctx))
		}
		return errors.Join(errs...)
	}

	slog.InfoContext(ctx, "OpenTelemetry tracing enabled",
		slog.String("service", serviceName()),
		slog.String("exporter", kind),
		slog.String("project_id", resolveProjectID()),
		slog.Bool("browser_span_replay", replayTP != nil))
	return shutdown, replayTP, nil
}

// ---- Seeded ID generator ----------------------------------------------------

type ctxKeyReplayTraceID struct{}
type ctxKeyReplaySpanID struct{}

// seededIDGenerator returns the trace/span ids stashed in the context by
// HandleIngestTraces, so a replayed browser span keeps the exact ids the SPA
// generated. For a span with a parent, the SDK calls NewSpanID (trace id is
// inherited from the parent context); for a root span it calls NewIDs.
type seededIDGenerator struct{}

func (seededIDGenerator) NewIDs(ctx context.Context) (oteltrace.TraceID, oteltrace.SpanID) {
	tid, _ := ctx.Value(ctxKeyReplayTraceID{}).(oteltrace.TraceID)
	sid, _ := ctx.Value(ctxKeyReplaySpanID{}).(oteltrace.SpanID)
	return tid, sid
}

func (seededIDGenerator) NewSpanID(ctx context.Context, _ oteltrace.TraceID) oteltrace.SpanID {
	sid, _ := ctx.Value(ctxKeyReplaySpanID{}).(oteltrace.SpanID)
	return sid
}

// ---- Browser span ingest ----------------------------------------------------

var hex16 = regexp.MustCompile(`^[0-9a-f]{16}$`)
var hex32 = regexp.MustCompile(`^[0-9a-f]{32}$`)

// browserSpan is one span emitted by the SPA tracer (frontend/src/services/tracing.ts).
type browserSpan struct {
	TraceID         string                 `json:"traceId"`
	SpanID          string                 `json:"spanId"`
	ParentSpanID    string                 `json:"parentSpanId"`
	Name            string                 `json:"name"`
	Kind            string                 `json:"kind"`
	StartTimeUnixMs float64                `json:"startTimeUnixMs"`
	EndTimeUnixMs   float64                `json:"endTimeUnixMs"`
	Attributes      map[string]interface{} `json:"attributes"`
}

type browserTraceBatch struct {
	Spans []browserSpan `json:"spans"`
}

// TelemetryIngest receives browser spans and forwards them so they correlate with
// the server/orchestrator spans of the same trace in Cloud Trace. When span
// export is enabled it re-emits each span as a real span through the replay
// tracer (native spans, #313); otherwise it records each as a trace-correlated
// log entry (the log-linkage fallback for local dev / no-export environments).
type TelemetryIngest struct {
	projectID string
	tracer    oteltrace.Tracer // nil => log-correlation fallback
}

// NewTelemetryIngest wires the ingest handler to the browser-replay provider from
// InitTracing. A nil replayTP (export disabled) keeps the handler on the
// log-correlation fallback.
func NewTelemetryIngest(replayTP *sdktrace.TracerProvider) *TelemetryIngest {
	ti := &TelemetryIngest{projectID: resolveProjectID()}
	if replayTP != nil {
		ti.tracer = replayTP.Tracer("browser-spa")
	}
	return ti
}

// cloudTraceField formats a trace id for Cloud Logging's trace-correlation field.
func (t *TelemetryIngest) cloudTraceField(traceID string) string {
	if t.projectID == "" {
		return traceID
	}
	return fmt.Sprintf("projects/%s/traces/%s", t.projectID, traceID)
}

// spanKindFromString maps the SPA's span kind string to an OTel SpanKind.
func spanKindFromString(k string) oteltrace.SpanKind {
	switch strings.ToLower(k) {
	case "client":
		return oteltrace.SpanKindClient
	case "server":
		return oteltrace.SpanKindServer
	case "producer":
		return oteltrace.SpanKindProducer
	case "consumer":
		return oteltrace.SpanKindConsumer
	default:
		return oteltrace.SpanKindInternal
	}
}

// browserAttributes converts the SPA span's JSON attribute map into typed OTel
// attributes. JSON numbers arrive as float64; everything else falls back to a
// string rendering so no attribute is silently dropped.
func browserAttributes(m map[string]interface{}) []attribute.KeyValue {
	if len(m) == 0 {
		return nil
	}
	attrs := make([]attribute.KeyValue, 0, len(m))
	for k, v := range m {
		switch val := v.(type) {
		case string:
			attrs = append(attrs, attribute.String(k, val))
		case bool:
			attrs = append(attrs, attribute.Bool(k, val))
		case float64:
			attrs = append(attrs, attribute.Float64(k, val))
		default:
			attrs = append(attrs, attribute.String(k, fmt.Sprintf("%v", val)))
		}
	}
	return attrs
}

// replaySpan re-emits a validated browser span as a real span, preserving its
// trace id, span id, and parent span id. It deliberately starts from a fresh
// context (not the HTTP request context): the parent must be the SPA-supplied
// parentSpanId, not the server's active request span — otherwise the browser
// span would be reparented under the server span, inverting the trace tree. The
// exported span therefore attaches under the SPA parent, and the server request
// span (parented to this span's id via the propagated traceparent) attaches
// under this one.
func (t *TelemetryIngest) replaySpan(s browserSpan) {
	tid, err := oteltrace.TraceIDFromHex(s.TraceID)
	if err != nil {
		return
	}
	sid, err := oteltrace.SpanIDFromHex(s.SpanID)
	if err != nil {
		return
	}

	genCtx := context.WithValue(context.Background(), ctxKeyReplayTraceID{}, tid)
	genCtx = context.WithValue(genCtx, ctxKeyReplaySpanID{}, sid)
	if s.ParentSpanID != "" {
		if psid, perr := oteltrace.SpanIDFromHex(s.ParentSpanID); perr == nil {
			parentSC := oteltrace.NewSpanContext(oteltrace.SpanContextConfig{
				TraceID:    tid,
				SpanID:     psid,
				TraceFlags: oteltrace.FlagsSampled,
				Remote:     true,
			})
			genCtx = oteltrace.ContextWithSpanContext(genCtx, parentSC)
		}
	}

	start := time.UnixMilli(int64(s.StartTimeUnixMs))
	end := time.UnixMilli(int64(s.EndTimeUnixMs))
	_, span := t.tracer.Start(genCtx, s.Name,
		oteltrace.WithSpanKind(spanKindFromString(s.Kind)),
		oteltrace.WithTimestamp(start),
	)
	span.SetAttributes(browserAttributes(s.Attributes)...)
	span.End(oteltrace.WithTimestamp(end))
}

// logSpan records a browser span as a trace-correlated structured log entry (the
// fallback used when span export is disabled). Reuses the structured-logging
// pipeline so the client span still surfaces in the trace view via log linkage.
func (t *TelemetryIngest) logSpan(reqCtx context.Context, s browserSpan) {
	logger := slog.Default().With(
		"logging.googleapis.com/trace", t.cloudTraceField(s.TraceID),
		"logging.googleapis.com/spanId", s.SpanID,
	)
	attrs := []any{
		slog.String("span.name", s.Name),
		slog.String("span.kind", s.Kind),
		slog.Float64("span.duration_ms", s.EndTimeUnixMs-s.StartTimeUnixMs),
	}
	if s.ParentSpanID != "" {
		attrs = append(attrs, slog.String("span.parent_id", s.ParentSpanID))
	}
	if len(s.Attributes) > 0 {
		attrs = append(attrs, slog.Any("span.attributes", s.Attributes))
	}
	logger.InfoContext(reqCtx, "browser_span", attrs...)
}

// HandleIngestTraces handles POST /api/telemetry/v1/traces.
//
// It forwards each valid browser span so the SPA's client spans surface in the
// same Cloud Trace timeline as the Go server and orchestrator spans: as a real
// span through the replay tracer when export is enabled (#313), or as a
// trace-correlated log entry otherwise. Malformed spans are skipped rather than
// failing the batch — telemetry must never break the page. Returns 202 with the
// number of spans accepted.
func (t *TelemetryIngest) HandleIngestTraces(c *gin.Context) {
	var batch browserTraceBatch
	if err := c.ShouldBindJSON(&batch); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid telemetry payload"})
		return
	}

	accepted := 0
	for _, s := range batch.Spans {
		if !hex32.MatchString(s.TraceID) || !hex16.MatchString(s.SpanID) {
			continue
		}
		if t.tracer != nil {
			t.replaySpan(s)
		} else {
			t.logSpan(c.Request.Context(), s)
		}
		accepted++
	}

	c.JSON(http.StatusAccepted, gin.H{"accepted": accepted})
}
