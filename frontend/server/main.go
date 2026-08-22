package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"

	"github.com/gin-gonic/gin"
	"go.opentelemetry.io/contrib/instrumentation/github.com/gin-gonic/gin/otelgin"
)

func main() {
	InitLogger()

	// Initialize OpenTelemetry: installs the W3C propagator (always) and, when a
	// destination is configured, a TracerProvider backed by the OTLP exporter
	// (OTEL_EXPORTER_OTLP_ENDPOINT) or the Cloud Trace exporter. replayTP re-emits
	// browser spans as real spans; nil when export is disabled. Shutdown flushes.
	ctx := context.Background()
	shutdownTracing, replayTP, err := InitTracing(ctx)
	if err != nil {
		slog.ErrorContext(ctx, "tracing init failed; continuing without span export", "error", err)
	}
	defer func() { _ = shutdownTracing(context.Background()) }()

	r := gin.New()
	// otelgin first so the server span (with any extracted `traceparent`) is in
	// the request context for the logging middleware and all handlers.
	r.Use(otelgin.Middleware(serviceName()), StructuredLogMiddleware(), gin.Recovery())

	srv := NewServer()
	oc := NewOrchestratorClient()
	ti := NewTelemetryIngest(replayTP)

	// Health check endpoint for Cloud Run
	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status": "ok",
		})
	})

	// Data endpoints for frontend
	r.GET("/api/holdings", srv.HandleGetHoldings)
	r.GET("/api/spending_report", srv.HandleGetSpendingReport)
	r.GET("/api/drift_report", srv.HandleGetDriftReport)
	r.GET("/api/documents", srv.HandleGetDocuments)
	r.POST("/api/documents", srv.HandleUploadDocument)
	r.GET("/api/profile", srv.HandleGetUserProfile)
	r.POST("/api/profile", srv.HandleSetUserProfile)
	r.POST("/api/profile/w2/upload", srv.HandleUploadW2)
	r.GET("/api/profile/w2", srv.HandleGetW2Documents)
	r.DELETE("/api/profile/w2/:id", srv.HandleDeleteW2Document)
	r.POST("/api/profile/w2/:id/apply", srv.HandleApplyW2ToProfile)
	r.GET("/api/onboarding", srv.HandleGetOnboarding)

	// Orchestrator bridge: streams ADK planner events back to the frontend as SSE.
	// Backend is either an HTTP orchestrator (ORCHESTRATOR_URL) or Agent Engine
	// (AGENT_ENGINE_ID); see plan.go for the selection logic.
	r.POST("/api/plan", oc.HandlePlan)
	r.POST("/api/plan/resume", oc.HandlePlanResume)

	// Structured wizard submission: bypasses the LLM interview and writes the
	// IPS directly via the same writer the LLM path uses. See onboarding.go.
	r.POST("/api/onboarding", oc.HandleApplyOnboarding)

	// Browser telemetry sink: the SPA posts its client spans here so they
	// correlate with server/orchestrator spans of the same trace. See telemetry.go.
	r.POST("/api/telemetry/v1/traces", ti.HandleIngestTraces)

	// Mount SPA static file serving and Vue client route fallback
	setupSPARoutes(r, "")

	// Run on dynamic PORT (Cloud Run default: 8080)
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	if err := r.Run(":" + port); err != nil {
		panic(err)
	}
}
