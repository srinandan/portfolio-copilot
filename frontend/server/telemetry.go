package main

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"regexp"

	texporter "github.com/GoogleCloudPlatform/opentelemetry-operations-go/exporter/trace"
	"github.com/gin-gonic/gin"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
)

// serviceName is the OpenTelemetry service.name reported for this process. It is
// what the correlated spans group under in Cloud Trace.
func serviceName() string {
	if n := os.Getenv("OTEL_SERVICE_NAME"); n != "" {
		return n
	}
	return "portfolio-copilot-frontend"
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

// tracingExportEnabled reports whether spans should be exported to Cloud Trace.
// Export requires a resolvable project and is opt-out via OTEL_TRACES_ENABLED=false.
// Trace-context PROPAGATION is always on regardless of this (see InitTracing).
func tracingExportEnabled() bool {
	if v := os.Getenv("OTEL_TRACES_ENABLED"); v == "false" || v == "0" {
		return false
	}
	return resolveProjectID() != ""
}

// InitTracing installs the global W3C TraceContext propagator and, when export is
// enabled, a Cloud Trace-backed TracerProvider. It returns a shutdown function
// that flushes pending spans.
//
// The propagator is installed unconditionally so `traceparent` flows
// browser -> Go server -> orchestrator even when this process does not export
// spans (e.g. local dev with no project). When export is disabled the returned
// shutdown is a no-op and the global provider stays the default no-op provider,
// so tracer.Start(...) calls elsewhere are cheap no-ops.
func InitTracing(ctx context.Context) (func(context.Context) error, error) {
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))

	noop := func(context.Context) error { return nil }

	if !tracingExportEnabled() {
		slog.InfoContext(ctx, "OpenTelemetry span export disabled; trace-context propagation active",
			slog.String("service", serviceName()))
		return noop, nil
	}

	projectID := resolveProjectID()
	exporter, err := texporter.New(texporter.WithProjectID(projectID))
	if err != nil {
		return noop, fmt.Errorf("cloud trace exporter init: %w", err)
	}

	res, err := resource.New(ctx,
		resource.WithAttributes(attribute.String("service.name", serviceName())),
		resource.WithTelemetrySDK(),
	)
	if err != nil {
		// A partial resource (e.g. schema conflict) is non-fatal — fall back to
		// just the service name rather than dropping tracing entirely.
		res = resource.NewSchemaless(attribute.String("service.name", serviceName()))
	}

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(res),
	)
	otel.SetTracerProvider(tp)

	slog.InfoContext(ctx, "OpenTelemetry tracing enabled (Cloud Trace)",
		slog.String("service", serviceName()),
		slog.String("project_id", projectID))
	return tp.Shutdown, nil
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

// TelemetryIngest receives browser spans and records them so they correlate with
// the server/orchestrator spans of the same trace in Cloud Trace.
type TelemetryIngest struct {
	projectID string
}

func NewTelemetryIngest() *TelemetryIngest {
	return &TelemetryIngest{projectID: resolveProjectID()}
}

// cloudTraceField formats a trace id for Cloud Logging's trace-correlation field.
func (t *TelemetryIngest) cloudTraceField(traceID string) string {
	if t.projectID == "" {
		return traceID
	}
	return fmt.Sprintf("projects/%s/traces/%s", t.projectID, traceID)
}

// HandleIngestTraces handles POST /api/telemetry/v1/traces.
//
// It records each valid browser span as a structured log entry carrying the
// Cloud Logging trace-correlation fields, so the SPA's client spans surface in
// the same Cloud Trace timeline as the Go server and orchestrator spans (the
// server continues the SPA's trace via the propagated `traceparent`). Malformed
// spans are skipped rather than failing the batch — telemetry must never break
// the page. Returns 202 with the number of spans accepted.
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
		logger.InfoContext(c.Request.Context(), "browser_span", attrs...)
		accepted++
	}

	c.JSON(http.StatusAccepted, gin.H{"accepted": accepted})
}
