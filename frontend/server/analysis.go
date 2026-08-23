package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
)

// EquityAnalysisRequest is the body the frontend POSTs to /api/analysis/equity.
type EquityAnalysisRequest struct {
	Ticker string `json:"ticker"`
	UserID string `json:"user_id,omitempty"`
}

// HandleAnalyzeEquity proxies POST /api/analysis/equity to the orchestrator's
// /v1/analysis/equity — a synchronous, deterministic advisory analysis (DCF
// valuation + suitability against the user's IPS/holdings). Advisory only: it
// never drafts or executes a trade. Mirrors HandleApplyOnboarding: a plain
// JSON request/response that bypasses the streaming planner.
func (c *OrchestratorClient) HandleAnalyzeEquity(ctx *gin.Context) {
	var req EquityAnalysisRequest
	if err := ctx.ShouldBindJSON(&req); err != nil {
		ctx.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	ticker := strings.ToUpper(strings.TrimSpace(req.Ticker))
	if ticker == "" {
		ctx.JSON(http.StatusBadRequest, gin.H{"error": "ticker is required"})
		return
	}
	userID := req.UserID
	if userID == "" {
		userID = ctx.DefaultQuery("user_id", "demo_user")
	}

	orchestratorURL := strings.TrimRight(c.directURL, "/")
	if orchestratorURL == "" {
		// Agent Engine mode doesn't expose a plain HTTP endpoint for this
		// deterministic path today; require ORCHESTRATOR_URL (same as onboarding).
		ctx.JSON(http.StatusServiceUnavailable, gin.H{
			"error": "equity analysis requires ORCHESTRATOR_URL to be set",
		})
		return
	}

	buf, err := json.Marshal(map[string]interface{}{"ticker": ticker, "user_id": userID})
	if err != nil {
		ctx.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("marshal failed: %v", err)})
		return
	}

	upstreamReq, err := http.NewRequestWithContext(
		ctx.Request.Context(),
		http.MethodPost,
		orchestratorURL+"/v1/analysis/equity",
		bytes.NewReader(buf),
	)
	if err != nil {
		ctx.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("build request failed: %v", err)})
		return
	}
	upstreamReq.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(upstreamReq)
	if err != nil {
		slog.ErrorContext(ctx.Request.Context(), "equity analysis call failed", "error", err)
		ctx.JSON(http.StatusBadGateway, gin.H{"error": fmt.Sprintf("orchestrator unreachable: %v", err)})
		return
	}
	defer resp.Body.Close()

	payload, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		slog.ErrorContext(ctx.Request.Context(),
			"orchestrator rejected equity analysis",
			"status", resp.StatusCode, "body", string(payload))
		ctx.Data(resp.StatusCode, resp.Header.Get("Content-Type"), payload)
		return
	}
	ctx.Data(resp.StatusCode, "application/json", payload)
}
