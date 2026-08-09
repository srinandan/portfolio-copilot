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

// OnboardingRequest is the wizard's collected state as posted by the frontend.
// It maps directly to the orchestrator's GoalsOnboardingResult plus the two
// approval-threshold fields that live on the IPS itself.
type OnboardingRequest struct {
	UserID                       string          `json:"user_id"`
	Result                       json.RawMessage `json:"result"`
	Trigger                      string          `json:"trigger,omitempty"`
	ApprovalRequiredAboveUSD     *float64        `json:"approval_required_above_usd,omitempty"`
	ApprovalRequiredAbovePercent *float64        `json:"approval_required_above_percent,omitempty"`
}

// HandleApplyOnboarding proxies POST /api/onboarding to the orchestrator's
// /v1/onboarding/apply, which persists the wizard result via
// write_ips_from_interview_result — same writer the LLM interview path uses.
//
// This skips the LLM entirely for the wizard case: the wizard already has
// structured data, so having a Managed Agent re-parse a prose serialization
// of it would just be a fragile round trip.
func (c *OrchestratorClient) HandleApplyOnboarding(ctx *gin.Context) {
	var req OnboardingRequest
	if err := ctx.ShouldBindJSON(&req); err != nil {
		ctx.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if len(req.Result) == 0 {
		ctx.JSON(http.StatusBadRequest, gin.H{"error": "result is required"})
		return
	}

	orchestratorURL := strings.TrimRight(c.directURL, "/")
	if orchestratorURL == "" {
		// Agent Engine mode doesn't expose a plain HTTP endpoint for direct
		// writes today; require ORCHESTRATOR_URL for the wizard path.
		ctx.JSON(http.StatusServiceUnavailable, gin.H{
			"error": "onboarding apply requires ORCHESTRATOR_URL to be set",
		})
		return
	}

	body := map[string]interface{}{
		"result":                          req.Result,
		"trigger":                         req.Trigger,
		"approval_required_above_usd":     req.ApprovalRequiredAboveUSD,
		"approval_required_above_percent": req.ApprovalRequiredAbovePercent,
	}
	if req.Trigger == "" {
		body["trigger"] = "initial"
	}
	buf, err := json.Marshal(body)
	if err != nil {
		ctx.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("marshal failed: %v", err)})
		return
	}

	upstreamReq, err := http.NewRequestWithContext(
		ctx.Request.Context(),
		http.MethodPost,
		orchestratorURL+"/v1/onboarding/apply",
		bytes.NewReader(buf),
	)
	if err != nil {
		ctx.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("build request failed: %v", err)})
		return
	}
	upstreamReq.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(upstreamReq)
	if err != nil {
		slog.ErrorContext(ctx.Request.Context(), "onboarding apply call failed", "error", err)
		ctx.JSON(http.StatusBadGateway, gin.H{"error": fmt.Sprintf("orchestrator unreachable: %v", err)})
		return
	}
	defer resp.Body.Close()

	payload, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		slog.ErrorContext(ctx.Request.Context(),
			"orchestrator rejected onboarding apply",
			"status", resp.StatusCode, "body", string(payload))
		ctx.Data(resp.StatusCode, resp.Header.Get("Content-Type"), payload)
		return
	}
	ctx.Data(resp.StatusCode, "application/json", payload)
}
