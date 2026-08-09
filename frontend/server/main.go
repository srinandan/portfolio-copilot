package main

import (
	"net/http"
	"os"

	"github.com/gin-gonic/gin"
)

func main() {
	InitLogger()

	r := gin.New()
	r.Use(StructuredLogMiddleware(), gin.Recovery())

	srv := NewServer()
	oc := NewOrchestratorClient()

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

	// Orchestrator bridge: streams ADK planner events back to the frontend as SSE.
	// Backend is either an HTTP orchestrator (ORCHESTRATOR_URL) or Agent Engine
	// (AGENT_ENGINE_ID); see plan.go for the selection logic.
	r.POST("/api/plan", oc.HandlePlan)
	r.POST("/api/plan/resume", oc.HandlePlanResume)

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
