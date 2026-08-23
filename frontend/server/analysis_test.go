package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
)

func analysisRouter(oc *OrchestratorClient) *gin.Engine {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.POST("/api/analysis/equity", oc.HandleAnalyzeEquity)
	return r
}

func TestHandleAnalyzeEquity_MissingTicker_Returns400(t *testing.T) {
	oc := &OrchestratorClient{directURL: "http://not-used", httpClient: http.DefaultClient}
	r := analysisRouter(oc)

	req := httptest.NewRequest(http.MethodPost, "/api/analysis/equity", strings.NewReader(`{"ticker":"  "}`))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d: %s", w.Code, w.Body.String())
	}
}

func TestHandleAnalyzeEquity_NoOrchestratorConfigured_Returns503(t *testing.T) {
	oc := &OrchestratorClient{httpClient: http.DefaultClient}
	r := analysisRouter(oc)

	req := httptest.NewRequest(http.MethodPost, "/api/analysis/equity", strings.NewReader(`{"ticker":"AAPL"}`))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusServiceUnavailable {
		t.Fatalf("expected 503, got %d: %s", w.Code, w.Body.String())
	}
}

func TestHandleAnalyzeEquity_DirectMode_ProxiesJSON(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/analysis/equity" {
			t.Errorf("unexpected upstream path %q", r.URL.Path)
		}
		var body map[string]interface{}
		_ = json.NewDecoder(r.Body).Decode(&body)
		if body["ticker"] != "AAPL" {
			t.Errorf("expected uppercased ticker AAPL, got %v", body["ticker"])
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ticker":"AAPL","recommendation":{"direction":"buy"}}`))
	}))
	defer upstream.Close()

	oc := &OrchestratorClient{directURL: upstream.URL, httpClient: http.DefaultClient}
	r := analysisRouter(oc)

	req := httptest.NewRequest(http.MethodPost, "/api/analysis/equity", strings.NewReader(`{"ticker":"aapl","user_id":"u1"}`))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	if !strings.Contains(w.Body.String(), `"direction":"buy"`) {
		t.Errorf("expected recommendation in body, got %s", w.Body.String())
	}
}

func TestHandleAnalyzeEquity_UpstreamError_PassesThrough(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusUnprocessableEntity)
		_, _ = w.Write([]byte(`{"detail":"No active IPS found"}`))
	}))
	defer upstream.Close()

	oc := &OrchestratorClient{directURL: upstream.URL, httpClient: http.DefaultClient}
	r := analysisRouter(oc)

	req := httptest.NewRequest(http.MethodPost, "/api/analysis/equity", strings.NewReader(`{"ticker":"AAPL"}`))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusUnprocessableEntity {
		t.Fatalf("expected 422 passthrough, got %d: %s", w.Code, w.Body.String())
	}
	if !strings.Contains(w.Body.String(), "No active IPS") {
		t.Errorf("expected upstream error passed through, got %s", w.Body.String())
	}
}
