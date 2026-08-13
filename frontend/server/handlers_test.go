package main

import (
	"bytes"
	"context"
	"encoding/json"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
	"portfolio-copilot/pkg/contracts"
)

func setupTestRouter() *gin.Engine {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	srv := NewServer()
	r.GET("/api/holdings", srv.HandleGetHoldings)
	r.GET("/api/spending_report", srv.HandleGetSpendingReport)
	r.GET("/api/drift_report", srv.HandleGetDriftReport)
	r.GET("/api/documents", srv.HandleGetDocuments)
	r.POST("/api/documents", srv.HandleUploadDocument)
	r.GET("/api/profile", srv.HandleGetUserProfile)
	r.POST("/api/profile", srv.HandleSetUserProfile)
	r.GET("/api/onboarding", srv.HandleGetOnboarding)
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

func TestGetUserProfileEndpoint(t *testing.T) {
	r := setupTestRouter()
	req, _ := http.NewRequest(http.MethodGet, "/api/profile?user_id=demo_user", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}

	var profile contracts.UserProfile
	if err := json.Unmarshal(w.Body.Bytes(), &profile); err != nil {
		t.Fatalf("failed to unmarshal UserProfile: %v", err)
	}
	if profile.UserID != "demo_user" {
		t.Errorf("expected UserID demo_user, got %s", profile.UserID)
	}
	if profile.FullName == "" {
		t.Errorf("expected non-empty FullName in profile")
	}
}

func TestSetUserProfileEndpoint_FallbackMode(t *testing.T) {
	r := setupTestRouter()
	body := `{"user_id":"demo_user","full_name":"Alex Mercer","age":46,"marital_status":"married"}`
	req, _ := http.NewRequest(http.MethodPost, "/api/profile", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", w.Code, w.Body.String())
	}
}

func TestSetUserProfileEndpoint_InvalidJSON(t *testing.T) {
	r := setupTestRouter()
	body := `{invalid json}`
	req, _ := http.NewRequest(http.MethodPost, "/api/profile", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected status 400, got %d", w.Code)
	}
}

func TestGetOnboardingEndpoint(t *testing.T) {
	r := setupTestRouter()
	req, _ := http.NewRequest(http.MethodGet, "/api/onboarding?user_id=demo_user", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}

	var profile contracts.OnboardingProfile
	if err := json.Unmarshal(w.Body.Bytes(), &profile); err != nil {
		t.Fatalf("failed to unmarshal OnboardingProfile: %v", err)
	}
	if !profile.HasActiveIPS {
		t.Errorf("expected has_active_ips to be true in fallback mode")
	}
	if len(profile.Goals) == 0 {
		t.Errorf("expected non-empty goals in onboarding profile")
	}
}

func createMultipartUpload(fieldName, filename, docType, targetTable string, content []byte) (*http.Request, error) {
	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)

	_ = writer.WriteField("document_type", docType)
	if targetTable != "" {
		_ = writer.WriteField("target_table", targetTable)
	}
	part, err := writer.CreateFormFile(fieldName, filename)
	if err != nil {
		return nil, err
	}
	if _, err := part.Write(content); err != nil {
		return nil, err
	}
	if err := writer.Close(); err != nil {
		return nil, err
	}

	req, err := http.NewRequest(http.MethodPost, "/api/documents", body)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())
	return req, nil
}

func TestUploadDocumentEndpoint_CSVTransactions(t *testing.T) {
	r := setupTestRouter()
	csvData := []byte("user_id,transaction_date,amount,description,raw_category,normalized_category\ndemo_user,2026-05-01,100.0,Test,Food,dining\n")
	req, err := createMultipartUpload("file", "transactions.csv", "transactions", "checking_transactions", csvData)
	if err != nil {
		t.Fatalf("failed to create multipart request: %v", err)
	}

	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", w.Code, w.Body.String())
	}

	var doc contracts.DocumentItem
	if err := json.Unmarshal(w.Body.Bytes(), &doc); err != nil {
		t.Fatalf("failed to unmarshal DocumentItem: %v", err)
	}
	if doc.Status != "SUCCESS" {
		t.Errorf("expected status SUCCESS, got %s", doc.Status)
	}
	if doc.RecordsParsed == nil || *doc.RecordsParsed != 1 {
		t.Errorf("expected 1 record parsed, got %v", doc.RecordsParsed)
	}
}

func TestUploadDocumentEndpoint_JSONHoldings(t *testing.T) {
	r := setupTestRouter()
	jsonData := []byte(`{"user_id":"demo_user","positions":[{"ticker":"AAPL","asset_class":"Equity","quantity":10}]}`)
	req, err := createMultipartUpload("file", "holdings.json", "holdings", "", jsonData)
	if err != nil {
		t.Fatalf("failed to create multipart request: %v", err)
	}

	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", w.Code, w.Body.String())
	}

	var doc contracts.DocumentItem
	if err := json.Unmarshal(w.Body.Bytes(), &doc); err != nil {
		t.Fatalf("failed to unmarshal DocumentItem: %v", err)
	}
	if doc.Status != "SUCCESS" || doc.RecordsParsed == nil || *doc.RecordsParsed != 1 {
		t.Errorf("unexpected doc item result: %+v", doc)
	}
}

func TestUploadDocumentEndpoint_InvalidExtension(t *testing.T) {
	r := setupTestRouter()
	req, err := createMultipartUpload("file", "test.pdf", "transactions", "", []byte("fake pdf"))
	if err != nil {
		t.Fatalf("failed to create multipart request: %v", err)
	}

	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected status 400, got %d", w.Code)
	}
}

func TestUploadDocumentEndpoint_InvalidJSON(t *testing.T) {
	r := setupTestRouter()
	req, err := createMultipartUpload("file", "holdings.json", "holdings", "", []byte("{invalid json}"))
	if err != nil {
		t.Fatalf("failed to create multipart request: %v", err)
	}

	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected status 400, got %d", w.Code)
	}
}

func TestUploadDocumentEndpoint_MissingDocType(t *testing.T) {
	r := setupTestRouter()
	req, _ := http.NewRequest(http.MethodPost, "/api/documents", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected status 400, got %d", w.Code)
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
	r.GET("/api/profile", srv.HandleGetUserProfile)
	r.GET("/api/onboarding", srv.HandleGetOnboarding)

	endpoints := []struct {
		method string
		path   string
	}{
		{http.MethodGet, "/api/holdings?user_id=usr_test"},
		{http.MethodGet, "/api/spending_report?user_id=usr_test"},
		{http.MethodGet, "/api/drift_report?user_id=usr_test"},
		{http.MethodGet, "/api/documents?user_id=usr_test"},
		{http.MethodGet, "/api/profile?user_id=usr_test"},
		{http.MethodGet, "/api/onboarding?user_id=usr_test"},
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
	r.GET("/api/profile", srv.HandleGetUserProfile)
	r.GET("/api/onboarding", srv.HandleGetOnboarding)

	endpoints := []struct {
		method string
		path   string
	}{
		{http.MethodGet, "/api/holdings?user_id=usr_test"},
		{http.MethodGet, "/api/spending_report?user_id=usr_test"},
		{http.MethodGet, "/api/drift_report?user_id=usr_test"},
		{http.MethodGet, "/api/documents?user_id=usr_test"},
		{http.MethodGet, "/api/profile?user_id=usr_test"},
		{http.MethodGet, "/api/onboarding?user_id=usr_test"},
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
