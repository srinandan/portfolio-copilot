package main

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
	"portfolio-copilot/pkg/contracts"
)

func setupTestRouter() *gin.Engine {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.Use(CORSMiddleware())
	srv := NewServer()
	r.GET("/api/holdings", srv.HandleGetHoldings)
	r.GET("/api/spending_report", srv.HandleGetSpendingReport)
	r.GET("/api/drift_report", srv.HandleGetDriftReport)
	r.GET("/api/documents", srv.HandleGetDocuments)
	return r
}

func TestGetHoldingsEndpoint(t *testing.T) {
	r := setupTestRouter()
	req, _ := http.NewRequest(http.MethodGet, "/api/holdings?user_id=test_user", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}

	var snapshot contracts.HoldingsSnapshot
	if err := json.Unmarshal(w.Body.Bytes(), &snapshot); err != nil {
		t.Fatalf("failed to unmarshal HoldingsSnapshot: %v", err)
	}
	if snapshot.TotalValueUSD == nil || *snapshot.TotalValueUSD <= 0 {
		t.Errorf("expected positive TotalValueUSD, got %v", snapshot.TotalValueUSD)
	}
	if len(snapshot.Positions) == 0 {
		t.Errorf("expected positions in holdings snapshot")
	}
}

func TestGetSpendingReportEndpoint(t *testing.T) {
	r := setupTestRouter()
	req, _ := http.NewRequest(http.MethodGet, "/api/spending_report", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}

	var report contracts.SpendingReport
	if err := json.Unmarshal(w.Body.Bytes(), &report); err != nil {
		t.Fatalf("failed to unmarshal SpendingReport: %v", err)
	}
	if report.TotalOutflowUSD <= 0 {
		t.Errorf("expected positive outflow, got %v", report.TotalOutflowUSD)
	}
	if len(report.CategoryBreakdown) == 0 {
		t.Errorf("expected category breakdown items")
	}
}

func TestGetDriftReportEndpoint(t *testing.T) {
	r := setupTestRouter()
	req, _ := http.NewRequest(http.MethodGet, "/api/drift_report", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}

	var report contracts.DriftReport
	if err := json.Unmarshal(w.Body.Bytes(), &report); err != nil {
		t.Fatalf("failed to unmarshal DriftReport: %v", err)
	}
	if len(report.Bands) == 0 {
		t.Errorf("expected bands in DriftReport")
	}
}

func TestGetDocumentsEndpoint(t *testing.T) {
	r := setupTestRouter()
	req, _ := http.NewRequest(http.MethodGet, "/api/documents", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}

	var docs []contracts.DocumentItem
	if err := json.Unmarshal(w.Body.Bytes(), &docs); err != nil {
		t.Fatalf("failed to unmarshal DocumentItem slice: %v", err)
	}
	if len(docs) == 0 {
		t.Errorf("expected non-empty document list")
	}
}

func TestCORSHeaders(t *testing.T) {
	r := setupTestRouter()
	req, _ := http.NewRequest(http.MethodOptions, "/api/holdings", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusNoContent {
		t.Fatalf("expected status 204 No Content for OPTIONS, got %d", w.Code)
	}
	if w.Header().Get("Access-Control-Allow-Origin") != "*" {
		t.Errorf("expected CORS Access-Control-Allow-Origin: *")
	}
}

func TestNewServer_WithProjectID(t *testing.T) {
	t.Setenv("FIRESTORE_PROJECT_ID", "test-project-id")
	srv := NewServer()
	if srv == nil {
		t.Fatalf("expected NewServer to return non-nil")
	}
}

func TestHandlers_WithStoreFallback(t *testing.T) {
	t.Setenv("FIRESTORE_PROJECT_ID", "test-project-id")
	srv := NewServer()

	r := gin.New()
	r.GET("/api/holdings", srv.HandleGetHoldings)
	r.GET("/api/spending_report", srv.HandleGetSpendingReport)
	r.GET("/api/drift_report", srv.HandleGetDriftReport)
	r.GET("/api/documents", srv.HandleGetDocuments)

	endpoints := []struct {
		method string
		path   string
	}{
		{http.MethodGet, "/api/holdings?user_id=usr_test"},
		{http.MethodGet, "/api/spending_report?user_id=usr_test"},
		{http.MethodGet, "/api/drift_report?user_id=usr_test"},
		{http.MethodGet, "/api/documents?user_id=usr_test"},
	}

	for _, ep := range endpoints {
		req, _ := http.NewRequest(ep.method, ep.path, nil)
		ctx, cancel := context.WithCancel(context.Background())
		cancel() // immediately cancel context to trigger non-NotFound upstream error
		req = req.WithContext(ctx)

		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		if w.Code != http.StatusBadGateway {
			t.Errorf("endpoint %s %s returned %d, expected 502 BadGateway on upstream error", ep.method, ep.path, w.Code)
		}
	}
}

func TestHandlers_NilStoreReturnsFallback(t *testing.T) {
	srv := &Server{Store: nil}

	r := gin.New()
	r.GET("/api/holdings", srv.HandleGetHoldings)
	r.GET("/api/spending_report", srv.HandleGetSpendingReport)
	r.GET("/api/drift_report", srv.HandleGetDriftReport)
	r.GET("/api/documents", srv.HandleGetDocuments)

	endpoints := []struct {
		method string
		path   string
	}{
		{http.MethodGet, "/api/holdings?user_id=usr_test"},
		{http.MethodGet, "/api/spending_report?user_id=usr_test"},
		{http.MethodGet, "/api/drift_report?user_id=usr_test"},
		{http.MethodGet, "/api/documents?user_id=usr_test"},
	}

	for _, ep := range endpoints {
		req, _ := http.NewRequest(ep.method, ep.path, nil)
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		if w.Code != http.StatusOK {
			t.Errorf("endpoint %s %s returned %d, expected 200 OK when Store is nil", ep.method, ep.path, w.Code)
		}
	}
}
