package main

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"strings"

	"github.com/gin-gonic/gin"
	"golang.org/x/oauth2/google"
)

// PlanRequest is the body the frontend POSTs to /api/plan and /api/plan/resume.
// user_id + message start a turn; resume adds session_id + invocation_id + interrupt_id + payload.
type PlanRequest struct {
	UserID       string          `json:"user_id"`
	Message      string          `json:"message,omitempty"`
	SessionID    string          `json:"session_id,omitempty"`
	InvocationID string          `json:"invocation_id,omitempty"`
	InterruptID  string          `json:"interrupt_id,omitempty"`
	Payload      json.RawMessage `json:"payload,omitempty"`
}

// OrchestratorClient talks to the orchestrator. Two modes:
//
//   * Direct HTTP: ORCHESTRATOR_URL set to a URL like http://localhost:8080 or the
//     internal URL of the orchestrator's FastAPI server. The gateway calls
//     <URL>/v1/invoke and <URL>/v1/resume, forwarding the SSE response as-is.
//   * Agent Engine streamQuery: AGENT_ENGINE_ID set to a full resource name
//     projects/<num>/locations/<region>/reasoningEngines/<id>. The gateway calls
//     https://<region>-aiplatform.googleapis.com/v1beta1/<name>:streamQuery with
//     an ADC bearer token, wraps the frontend body in the reasoning-engine input
//     envelope, and forwards the streamed JSON payloads as SSE.
//
// One of the two must be configured; the handler returns 503 otherwise.
type OrchestratorClient struct {
	directURL     string
	agentEngineID string
	httpClient    *http.Client
	tokenSource   func(context.Context) (string, error)
}

func NewOrchestratorClient() *OrchestratorClient {
	return &OrchestratorClient{
		directURL:     os.Getenv("ORCHESTRATOR_URL"),
		agentEngineID: os.Getenv("AGENT_ENGINE_ID"),
		httpClient:    &http.Client{},
		tokenSource:   defaultAccessToken,
	}
}

func defaultAccessToken(ctx context.Context) (string, error) {
	creds, err := google.FindDefaultCredentials(ctx, "https://www.googleapis.com/auth/cloud-platform")
	if err != nil {
		return "", fmt.Errorf("find default credentials: %w", err)
	}
	tok, err := creds.TokenSource.Token()
	if err != nil {
		return "", fmt.Errorf("fetch access token: %w", err)
	}
	return tok.AccessToken, nil
}

// agentEngineRegion extracts "us-central1" from
// "projects/.../locations/us-central1/reasoningEngines/...".
func agentEngineRegion(name string) (string, error) {
	parts := strings.Split(name, "/")
	for i, p := range parts {
		if p == "locations" && i+1 < len(parts) {
			return parts[i+1], nil
		}
	}
	return "", fmt.Errorf("no /locations/<region>/ in %q", name)
}

// invokeDirect sends the plan request to a plain HTTP orchestrator (dev mode).
// Returns the streaming SSE body; the caller writes it to the frontend as-is.
func (c *OrchestratorClient) invokeDirect(ctx context.Context, path string, body PlanRequest) (io.ReadCloser, string, int, error) {
	buf, err := json.Marshal(body)
	if err != nil {
		return nil, "", 0, err
	}
	url := strings.TrimRight(c.directURL, "/") + path
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(buf))
	if err != nil {
		return nil, "", 0, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "text/event-stream")
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, "", 0, err
	}
	return resp.Body, resp.Header.Get("Content-Type"), resp.StatusCode, nil
}

// invokeAgentEngine sends the plan request to Agent Platform Agent Runtime's :streamQuery
// endpoint and returns the raw streamed body (newline-delimited JSON), plus status.
// Caller must adapt the JSON stream to SSE — see writeAgentEngineSSE.
func (c *OrchestratorClient) invokeAgentEngine(ctx context.Context, body PlanRequest, resume bool) (io.ReadCloser, int, error) {
	region, err := agentEngineRegion(c.agentEngineID)
	if err != nil {
		return nil, 0, err
	}
	classMethod := "invoke"
	if resume {
		classMethod = "resume"
	}
	envelope := map[string]interface{}{
		"class_method": classMethod,
		"input":        body,
	}
	buf, err := json.Marshal(envelope)
	if err != nil {
		return nil, 0, err
	}
	url := fmt.Sprintf(
		"https://%s-aiplatform.googleapis.com/v1beta1/%s:streamQuery",
		region, c.agentEngineID,
	)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(buf))
	if err != nil {
		return nil, 0, err
	}
	tok, err := c.tokenSource(ctx)
	if err != nil {
		return nil, 0, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+tok)
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, 0, err
	}
	return resp.Body, resp.StatusCode, nil
}

// writeSSEPassthrough forwards an SSE body 1:1 to the ResponseWriter, flushing
// after each read. Used for direct-HTTP mode where the orchestrator already
// speaks SSE.
func writeSSEPassthrough(c *gin.Context, body io.ReadCloser) {
	defer body.Close()
	buf := make([]byte, 4096)
	for {
		select {
		case <-c.Request.Context().Done():
			return
		default:
		}
		n, err := body.Read(buf)
		if n > 0 {
			if _, werr := c.Writer.Write(buf[:n]); werr != nil {
				return
			}
			c.Writer.Flush()
		}
		if err == io.EOF {
			return
		}
		if err != nil {
			slog.WarnContext(c.Request.Context(), "orchestrator stream read error", "error", err)
			return
		}
	}
}

// writeAgentEngineSSE reads the newline-delimited JSON stream returned by
// :streamQuery and re-emits each object as a single SSE `data:` frame.
func writeAgentEngineSSE(c *gin.Context, body io.ReadCloser) {
	defer body.Close()
	scanner := bufio.NewScanner(body)
	scanner.Buffer(make([]byte, 1024*1024), 8*1024*1024)
	for scanner.Scan() {
		select {
		case <-c.Request.Context().Done():
			return
		default:
		}
		line := bytes.TrimSpace(scanner.Bytes())
		if len(line) == 0 {
			continue
		}
		if _, err := fmt.Fprintf(c.Writer, "data: %s\n\n", line); err != nil {
			return
		}
		c.Writer.Flush()
	}
	if err := scanner.Err(); err != nil {
		slog.WarnContext(c.Request.Context(), "agent-engine stream scan error", "error", err)
	}
}

// runPlan is the shared handler body for /api/plan and /api/plan/resume.
// resume=true switches the endpoint suffix (/v1/resume in direct mode, class_method="resume"
// on Agent Engine).
func (c *OrchestratorClient) runPlan(ctx *gin.Context, req PlanRequest, resume bool) {
	if req.UserID == "" {
		ctx.JSON(http.StatusBadRequest, gin.H{"error": "user_id required"})
		return
	}
	if c.directURL == "" && c.agentEngineID == "" {
		ctx.JSON(http.StatusServiceUnavailable, gin.H{
			"error": "orchestrator not configured; set ORCHESTRATOR_URL or AGENT_ENGINE_ID",
		})
		return
	}

	// SSE headers
	ctx.Writer.Header().Set("Content-Type", "text/event-stream")
	ctx.Writer.Header().Set("Cache-Control", "no-cache")
	ctx.Writer.Header().Set("Connection", "keep-alive")
	ctx.Writer.Header().Set("X-Accel-Buffering", "no")
	ctx.Writer.Flush()

	if c.directURL != "" {
		path := "/v1/invoke"
		if resume {
			path = "/v1/resume"
		}
		body, contentType, status, err := c.invokeDirect(ctx.Request.Context(), path, req)
		if err != nil {
			logAndWriteSSEError(ctx, fmt.Sprintf("orchestrator call failed: %v", err),
				"mode", "direct", "path", path, "user_id", req.UserID, "error", err)
			return
		}
		if status >= 400 {
			payload, _ := io.ReadAll(body)
			body.Close()
			logAndWriteSSEError(ctx, fmt.Sprintf("orchestrator %d: %s", status, string(payload)),
				"mode", "direct", "path", path, "user_id", req.UserID, "status", status, "body", string(payload))
			return
		}
		if !strings.HasPrefix(contentType, "text/event-stream") {
			payload, _ := io.ReadAll(body)
			body.Close()
			logAndWriteSSEError(ctx,
				fmt.Sprintf("orchestrator returned unexpected content-type %q: %s", contentType, string(payload)),
				"mode", "direct", "path", path, "user_id", req.UserID, "content_type", contentType, "body", string(payload))
			return
		}
		// The orchestrator already speaks SSE — pass through untouched.
		writeSSEPassthrough(ctx, body)
		return
	}

	// Agent Engine mode
	body, status, err := c.invokeAgentEngine(ctx.Request.Context(), req, resume)
	if err != nil {
		logAndWriteSSEError(ctx, fmt.Sprintf("agent engine call failed: %v", err),
			"mode", "agent_engine", "engine_id", c.agentEngineID, "resume", resume, "user_id", req.UserID, "error", err)
		return
	}
	defer body.Close()
	if status >= 400 {
		payload, _ := io.ReadAll(body)
		logAndWriteSSEError(ctx, fmt.Sprintf("agent engine %d: %s", status, string(payload)),
			"mode", "agent_engine", "engine_id", c.agentEngineID, "resume", resume, "user_id", req.UserID,
			"status", status, "body", string(payload))
		return
	}
	writeAgentEngineSSE(ctx, body)
}

// logAndWriteSSEError logs the failure at ERROR with structured context and
// then writes the SSE `error` frame the frontend expects. Splitting the two
// paths (log + wire) is what was missing — the wire frame was surfacing the
// error to users but nothing was hitting Cloud Logging, so operators had no
// way to see e.g. an Agent Registry 401 or a bad Agent Engine IAM binding.
func logAndWriteSSEError(ctx *gin.Context, msg string, kv ...any) {
	slog.ErrorContext(ctx.Request.Context(), msg, kv...)
	writeSSEError(ctx, msg)
}

func writeSSEError(ctx *gin.Context, msg string) {
	payload, _ := json.Marshal(gin.H{"error": msg})
	fmt.Fprintf(ctx.Writer, "event: error\ndata: %s\n\n", string(payload))
	ctx.Writer.Flush()
}

// HandlePlan handles POST /api/plan — starts a new planning turn.
func (c *OrchestratorClient) HandlePlan(ctx *gin.Context) {
	var req PlanRequest
	if err := ctx.ShouldBindJSON(&req); err != nil {
		ctx.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.runPlan(ctx, req, false)
}

// HandlePlanResume handles POST /api/plan/resume — resumes a HITL-paused session.
func (c *OrchestratorClient) HandlePlanResume(ctx *gin.Context) {
	var req PlanRequest
	if err := ctx.ShouldBindJSON(&req); err != nil {
		ctx.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if req.SessionID == "" || req.InvocationID == "" || req.InterruptID == "" {
		ctx.JSON(http.StatusBadRequest, gin.H{
			"error": "session_id, invocation_id and interrupt_id are required for resume",
		})
		return
	}
	c.runPlan(ctx, req, true)
}
