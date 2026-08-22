package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	cloudbigquery "cloud.google.com/go/bigquery"
	"github.com/gin-gonic/gin"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"portfolio-copilot/pkg/bigquery"
	"portfolio-copilot/pkg/contracts"
	"portfolio-copilot/pkg/documentai"
	"portfolio-copilot/pkg/store"
)

var errMockNotFound = status.Error(codes.NotFound, "not found")

var _ store.Store = (*mockStore)(nil)
var _ bigquery.Runner = (*mockBQRunner)(nil)

// mockStore implements store.Store for unit tests.
type mockStore struct {
	documents       map[string]contracts.DocumentItem
	holdings        map[string]*contracts.HoldingsSnapshot
	liabilities     map[string]*contracts.LiabilitiesSnapshot
	ips             map[string]*contracts.InvestmentPolicyStatement
	profiles        map[string]*contracts.UserProfile
	spendingReports map[string]*contracts.SpendingReport
	driftReports    map[string]*contracts.DriftReport
	w2Docs          map[string]contracts.W2Document
	failAll         bool
}

func newMockStore() *mockStore {
	return &mockStore{
		documents:       make(map[string]contracts.DocumentItem),
		holdings:        make(map[string]*contracts.HoldingsSnapshot),
		liabilities:     make(map[string]*contracts.LiabilitiesSnapshot),
		ips:             make(map[string]*contracts.InvestmentPolicyStatement),
		profiles:        make(map[string]*contracts.UserProfile),
		spendingReports: make(map[string]*contracts.SpendingReport),
		driftReports:    make(map[string]*contracts.DriftReport),
		w2Docs:          make(map[string]contracts.W2Document),
	}
}

func (m *mockStore) GetHoldings(ctx context.Context, userID string) (*contracts.HoldingsSnapshot, error) {
	if m.failAll {
		return nil, errors.New("mock upstream error")
	}
	h, ok := m.holdings[userID]
	if !ok {
		return nil, errMockNotFound
	}
	return h, nil
}

func (m *mockStore) SetHoldings(ctx context.Context, userID string, snapshot *contracts.HoldingsSnapshot) error {
	if m.failAll {
		return errors.New("mock upstream error")
	}
	m.holdings[userID] = snapshot
	return nil
}

func (m *mockStore) GetSpendingReport(ctx context.Context, userID string) (*contracts.SpendingReport, error) {
	if m.failAll {
		return nil, errors.New("mock upstream error")
	}
	r, ok := m.spendingReports[userID]
	if !ok {
		return nil, errMockNotFound
	}
	return r, nil
}

func (m *mockStore) GetDriftReport(ctx context.Context, userID string) (*contracts.DriftReport, error) {
	if m.failAll {
		return nil, errors.New("mock upstream error")
	}
	r, ok := m.driftReports[userID]
	if !ok {
		return nil, errMockNotFound
	}
	return r, nil
}

func (m *mockStore) GetDocuments(ctx context.Context, userID string) ([]contracts.DocumentItem, error) {
	if m.failAll {
		return nil, errors.New("mock upstream error")
	}
	var res []contracts.DocumentItem
	for _, doc := range m.documents {
		if doc.UserID == userID {
			res = append(res, doc)
		}
	}
	return res, nil
}

func (m *mockStore) SetDocument(ctx context.Context, item *contracts.DocumentItem) error {
	if m.failAll {
		return errors.New("mock upstream error")
	}
	m.documents[item.ID] = *item
	return nil
}

func (m *mockStore) GetActiveIPS(ctx context.Context, userID string) (*contracts.InvestmentPolicyStatement, error) {
	if m.failAll {
		return nil, errors.New("mock upstream error")
	}
	ips, ok := m.ips[userID]
	if !ok {
		return nil, errMockNotFound
	}
	return ips, nil
}

func (m *mockStore) UpdateIPS(ctx context.Context, ips *contracts.InvestmentPolicyStatement) error {
	if m.failAll {
		return errors.New("mock upstream error")
	}
	m.ips[ips.UserID] = ips
	return nil
}

func (m *mockStore) GetLiabilities(ctx context.Context, userID string) (*contracts.LiabilitiesSnapshot, error) {
	if m.failAll {
		return nil, errors.New("mock upstream error")
	}
	l, ok := m.liabilities[userID]
	if !ok {
		return nil, errMockNotFound
	}
	return l, nil
}

func (m *mockStore) SetLiabilities(ctx context.Context, userID string, snapshot *contracts.LiabilitiesSnapshot) error {
	if m.failAll {
		return errors.New("mock upstream error")
	}
	m.liabilities[userID] = snapshot
	return nil
}

func (m *mockStore) GetUserProfile(ctx context.Context, userID string) (*contracts.UserProfile, error) {
	if m.failAll {
		return nil, errors.New("mock upstream error")
	}
	p, ok := m.profiles[userID]
	if !ok {
		return nil, errMockNotFound
	}
	return p, nil
}

func (m *mockStore) SetUserProfile(ctx context.Context, userID string, profile *contracts.UserProfile) error {
	if m.failAll {
		return errors.New("mock upstream error")
	}
	m.profiles[userID] = profile
	return nil
}

func (m *mockStore) AppendAuditLog(ctx context.Context, entry *contracts.AuditLogEntry) error {
	if m.failAll {
		return errors.New("mock upstream error")
	}
	return nil
}

func (m *mockStore) SetW2Document(ctx context.Context, doc *contracts.W2Document) error {
	if m.failAll {
		return errors.New("mock upstream error")
	}
	m.w2Docs[doc.ID] = *doc
	return nil
}

func (m *mockStore) GetW2Documents(ctx context.Context, userID string) ([]contracts.W2Document, error) {
	if m.failAll {
		return nil, errors.New("mock upstream error")
	}
	var res []contracts.W2Document
	for _, doc := range m.w2Docs {
		if doc.UserID == userID {
			res = append(res, doc)
		}
	}
	return res, nil
}

func (m *mockStore) GetW2Document(ctx context.Context, userID string, docID string) (*contracts.W2Document, error) {
	if m.failAll {
		return nil, errors.New("mock upstream error")
	}
	doc, ok := m.w2Docs[docID]
	if !ok {
		return nil, errMockNotFound
	}
	if doc.UserID != userID {
		return nil, errors.New("permission denied")
	}
	return &doc, nil
}

func (m *mockStore) DeleteW2Document(ctx context.Context, userID string, docID string) error {
	if m.failAll {
		return errors.New("mock upstream error")
	}
	doc, ok := m.w2Docs[docID]
	if !ok {
		return errMockNotFound
	}
	if doc.UserID != userID {
		return errors.New("permission denied")
	}
	delete(m.w2Docs, docID)
	return nil
}

// mockBQRunner implements bigquery.Runner for unit tests.
type mockBQRunner struct {
	insertedRows []bigquery.TransactionRecord
	failInsert   bool
}

func newMockBQRunner() *mockBQRunner {
	return &mockBQRunner{}
}

func (m *mockBQRunner) RunSecureQuery(ctx context.Context, generatedSQL, userID string) ([]map[string]cloudbigquery.Value, error) {
	return nil, nil
}

func (m *mockBQRunner) InsertTransactions(ctx context.Context, datasetName, tableName string, rows []bigquery.TransactionRecord) error {
	if m.failInsert {
		return errors.New("mock BigQuery insert error")
	}
	m.insertedRows = append(m.insertedRows, rows...)
	return nil
}

func setupTestRouterWithServer(srv *Server) *gin.Engine {
	gin.SetMode(gin.TestMode)
	r := gin.New()
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
	return r
}

func setupTestRouter() *gin.Engine {
	return setupTestRouterWithServer(NewServer())
}

func createMultipartUpload(fieldName, filename, docType, targetTable, userID string, content []byte) (*http.Request, error) {
	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)

	_ = writer.WriteField("document_type", docType)
	if targetTable != "" {
		_ = writer.WriteField("target_table", targetTable)
	}
	if userID != "" {
		_ = writer.WriteField("user_id", userID)
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
}

func TestGetSpendingReportEndpoint(t *testing.T) {
	r := setupTestRouter()
	req, _ := http.NewRequest(http.MethodGet, "/api/spending_report", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
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
}

func TestGetDocumentsEndpoint_UserScoping(t *testing.T) {
	mock := newMockStore()
	mock.documents["doc-alice"] = contracts.DocumentItem{
		ID:       "doc-alice",
		UserID:   "alice",
		Filename: "alice.csv",
		Status:   "SUCCESS",
	}
	mock.documents["doc-bob"] = contracts.DocumentItem{
		ID:       "doc-bob",
		UserID:   "bob",
		Filename: "bob.csv",
		Status:   "SUCCESS",
	}

	srv := &Server{Store: mock}
	r := setupTestRouterWithServer(srv)

	req, _ := http.NewRequest(http.MethodGet, "/api/documents?user_id=alice", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}

	var docs []contracts.DocumentItem
	if err := json.Unmarshal(w.Body.Bytes(), &docs); err != nil {
		t.Fatalf("failed to unmarshal DocumentItem slice: %v", err)
	}
	if len(docs) != 1 || docs[0].UserID != "alice" {
		t.Errorf("expected 1 document for alice, got %v", docs)
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
}

func TestSetUserProfileEndpoint_WithMockStore(t *testing.T) {
	mock := newMockStore()
	srv := &Server{Store: mock}
	r := setupTestRouterWithServer(srv)

	body := `{"user_id":"demo_user","full_name":"Alex Mercer","age":46,"marital_status":"married"}`
	req, _ := http.NewRequest(http.MethodPost, "/api/profile", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", w.Code, w.Body.String())
	}
	if mock.profiles["demo_user"] == nil || mock.profiles["demo_user"].FullName != "Alex Mercer" {
		t.Errorf("expected profile saved to mock store")
	}
}

func TestGetOnboardingEndpoint_NilStoreReturnsHasActiveIPSFalse(t *testing.T) {
	srv := &Server{Store: nil}
	r := setupTestRouterWithServer(srv)

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
	if profile.HasActiveIPS {
		t.Errorf("expected HasActiveIPS=false in nil store mode")
	}
}

func TestGetOnboardingEndpoint_WithActiveIPS(t *testing.T) {
	mock := newMockStore()
	mock.ips["demo_user"] = &contracts.InvestmentPolicyStatement{
		IPSID:            "ips_123",
		UserID:           "demo_user",
		Version:          1,
		TimeHorizonYears: 10,
		RiskTolerance:    contracts.RiskToleranceAggressive,
		Goals: []contracts.Goal{
			{Name: "House", TargetAmountUSD: 500000, TargetDate: "2030-01-01"},
		},
		Constraints: contracts.Constraints{
			ConcentrationLimitPercent: 20,
		},
	}
	srv := &Server{Store: mock}
	r := setupTestRouterWithServer(srv)

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
	if !profile.HasActiveIPS || profile.IPSID != "ips_123" {
		t.Errorf("expected HasActiveIPS=true with IPSID ips_123, got %+v", profile)
	}
	if profile.Constraints == nil || profile.Constraints.ConcentrationLimitPercent != 20 {
		t.Errorf("expected constraints pointer with concentration limit 20, got %+v", profile.Constraints)
	}
}

func TestUploadDocumentEndpoint_CSVTransactions_SuccessAndBigQueryIngestion(t *testing.T) {
	mock := newMockStore()
	mockBQ := newMockBQRunner()
	srv := &Server{Store: mock, BQRunner: mockBQ}
	r := setupTestRouterWithServer(srv)

	csvData := []byte("user_id,transaction_date,amount,description,raw_category,normalized_category\nfake_user,2026-05-01,100.50,Grocery Store,Food,groceries\n")
	req, err := createMultipartUpload("file", "transactions.csv", "transactions", "checking_transactions", "demo_user", csvData)
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
		t.Errorf("expected SUCCESS with 1 record, got %+v", doc)
	}
	if doc.UserID != "demo_user" {
		t.Errorf("expected doc.UserID demo_user, got %s", doc.UserID)
	}

	// Verify row landed in BigQuery mock runner scoped to request user
	if len(mockBQ.insertedRows) != 1 {
		t.Fatalf("expected 1 row inserted into BigQuery, got %d", len(mockBQ.insertedRows))
	}
	inserted := mockBQ.insertedRows[0]
	if inserted.UserID != "demo_user" {
		t.Errorf("expected inserted row UserID to be scoped to 'demo_user', got %s", inserted.UserID)
	}
	if inserted.Amount != 100.50 || inserted.NormalizedCategory != "groceries" {
		t.Errorf("unexpected inserted row values: %+v", inserted)
	}

	// Verify doc audit saved in store
	if len(mock.documents) != 1 {
		t.Errorf("expected 1 doc audit item in mock store")
	}
}

func TestUploadDocumentEndpoint_CSVTransactions_NilBQRunnerReturns503(t *testing.T) {
	mock := newMockStore()
	srv := &Server{Store: mock, BQRunner: nil}
	r := setupTestRouterWithServer(srv)

	csvData := []byte("user_id,transaction_date,amount,description,raw_category,normalized_category\ndemo_user,2026-05-01,100.50,Grocery,Food,groceries\n")
	req, _ := createMultipartUpload("file", "test.csv", "transactions", "checking_transactions", "demo_user", csvData)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusServiceUnavailable {
		t.Fatalf("expected status 503 when BQRunner is nil for transactions, got %d", w.Code)
	}
}

func TestUploadDocumentEndpoint_CSVTransactions_InvalidHeader(t *testing.T) {
	mock := newMockStore()
	mockBQ := newMockBQRunner()
	srv := &Server{Store: mock, BQRunner: mockBQ}
	r := setupTestRouterWithServer(srv)

	// Wrong column count
	csvData := []byte("col1,col2\nval1,val2\n")
	req, _ := createMultipartUpload("file", "bad.csv", "transactions", "checking_transactions", "demo_user", csvData)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected status 400 for bad header count, got %d", w.Code)
	}

	// Misordered columns
	csvData2 := []byte("user_id,amount,transaction_date,description,raw_category,normalized_category\ndemo_user,100.0,2026-05-01,Grocery,Food,groceries\n")
	req2, _ := createMultipartUpload("file", "misordered.csv", "transactions", "checking_transactions", "demo_user", csvData2)
	w2 := httptest.NewRecorder()
	r.ServeHTTP(w2, req2)

	if w2.Code != http.StatusBadRequest {
		t.Fatalf("expected status 400 for misordered header, got %d", w2.Code)
	}
}

func TestUploadDocumentEndpoint_CSVTransactions_InvalidDateFormat(t *testing.T) {
	mock := newMockStore()
	mockBQ := newMockBQRunner()
	srv := &Server{Store: mock, BQRunner: mockBQ}
	r := setupTestRouterWithServer(srv)

	csvData := []byte("user_id,transaction_date,amount,description,raw_category,normalized_category\ndemo_user,05/01/2026,100.50,Grocery,Food,groceries\n")
	req, _ := createMultipartUpload("file", "bad.csv", "transactions", "checking_transactions", "demo_user", csvData)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected status 400 for bad date format, got %d", w.Code)
	}
}

func TestUploadDocumentEndpoint_CSVTransactions_InvalidAmount(t *testing.T) {
	mock := newMockStore()
	mockBQ := newMockBQRunner()
	srv := &Server{Store: mock, BQRunner: mockBQ}
	r := setupTestRouterWithServer(srv)

	csvData := []byte("user_id,transaction_date,amount,description,raw_category,normalized_category\ndemo_user,2026-05-01,notanumber,Grocery,Food,groceries\n")
	req, _ := createMultipartUpload("file", "bad.csv", "transactions", "checking_transactions", "demo_user", csvData)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected status 400 for invalid amount, got %d", w.Code)
	}
}

func TestUploadDocumentEndpoint_CSVTransactions_BigQueryFailure(t *testing.T) {
	mock := newMockStore()
	mockBQ := newMockBQRunner()
	mockBQ.failInsert = true
	srv := &Server{Store: mock, BQRunner: mockBQ}
	r := setupTestRouterWithServer(srv)

	csvData := []byte("user_id,transaction_date,amount,description,raw_category,normalized_category\ndemo_user,2026-05-01,100.50,Grocery,Food,groceries\n")
	req, _ := createMultipartUpload("file", "test.csv", "transactions", "checking_transactions", "demo_user", csvData)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected status 400 on BigQuery failure, got %d", w.Code)
	}
}

func TestUploadDocumentEndpoint_JSONHoldings_OverridesBodyUserID(t *testing.T) {
	mock := newMockStore()
	srv := &Server{Store: mock}
	r := setupTestRouterWithServer(srv)

	// Attacker tries to pass "victim_user" inside the JSON body
	jsonData := []byte(`{"user_id":"victim_user","positions":[{"ticker":"AAPL","asset_class":"Equity","quantity":10}]}`)
	req, _ := createMultipartUpload("file", "holdings.json", "holdings", "", "demo_user", jsonData)

	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", w.Code, w.Body.String())
	}

	// Must be stored under "demo_user" (authenticated request user), NOT "victim_user"
	if mock.holdings["victim_user"] != nil {
		t.Fatalf("CRITICAL IDOR: holdings were saved under body user_id 'victim_user' instead of request identity!")
	}
	if mock.holdings["demo_user"] == nil || len(mock.holdings["demo_user"].Positions) != 1 {
		t.Fatalf("expected holdings saved under request user 'demo_user'")
	}
}

func TestUploadDocumentEndpoint_JSONLiabilities_OverridesBodyUserID(t *testing.T) {
	mock := newMockStore()
	srv := &Server{Store: mock}
	r := setupTestRouterWithServer(srv)

	jsonData := []byte(`{"user_id":"victim_user","liabilities":[{"liability_id":"l1","type":"mortgage","balance_usd":1000}]}`)
	req, _ := createMultipartUpload("file", "liabilities.json", "liabilities", "", "demo_user", jsonData)

	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", w.Code, w.Body.String())
	}

	if mock.liabilities["victim_user"] != nil {
		t.Fatalf("CRITICAL IDOR: liabilities were saved under body user_id 'victim_user'!")
	}
	if mock.liabilities["demo_user"] == nil {
		t.Fatalf("expected liabilities saved under request user 'demo_user'")
	}
}

func TestUploadDocumentEndpoint_JSONIPS_OverridesBodyUserID(t *testing.T) {
	mock := newMockStore()
	srv := &Server{Store: mock}
	r := setupTestRouterWithServer(srv)

	jsonData := []byte(`{"user_id":"victim_user","ips_id":"ips_1","version":1}`)
	req, _ := createMultipartUpload("file", "ips.json", "ips", "", "demo_user", jsonData)

	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", w.Code, w.Body.String())
	}

	if mock.ips["victim_user"] != nil {
		t.Fatalf("CRITICAL IDOR: IPS was saved under body user_id 'victim_user'!")
	}
	if mock.ips["demo_user"] == nil {
		t.Fatalf("expected IPS saved under request user 'demo_user'")
	}
}

func TestUploadDocumentEndpoint_NilStoreReturns503(t *testing.T) {
	srv := &Server{Store: nil}
	r := setupTestRouterWithServer(srv)

	csvData := []byte("user_id,transaction_date,amount,description,raw_category,normalized_category\ndemo_user,2026-05-01,100.0,Test,Food,dining\n")
	req, _ := createMultipartUpload("file", "transactions.csv", "transactions", "checking_transactions", "demo_user", csvData)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusServiceUnavailable {
		t.Fatalf("expected status 503 when Store is nil, got %d: %s", w.Code, w.Body.String())
	}
}

func TestUploadDocumentEndpoint_InvalidExtension(t *testing.T) {
	mock := newMockStore()
	srv := &Server{Store: mock}
	r := setupTestRouterWithServer(srv)

	req, _ := createMultipartUpload("file", "test.pdf", "transactions", "", "demo_user", []byte("fake pdf"))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected status 400, got %d", w.Code)
	}
}

func TestUploadDocumentEndpoint_InvalidJSON(t *testing.T) {
	mock := newMockStore()
	srv := &Server{Store: mock}
	r := setupTestRouterWithServer(srv)

	req, _ := createMultipartUpload("file", "holdings.json", "holdings", "", "demo_user", []byte("{invalid json}"))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected status 400, got %d", w.Code)
	}
}

func TestUploadDocumentEndpoint_MissingDocType(t *testing.T) {
	mock := newMockStore()
	srv := &Server{Store: mock}
	r := setupTestRouterWithServer(srv)

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
	mock := newMockStore()
	mock.failAll = true
	srv := &Server{Store: mock}
	r := setupTestRouterWithServer(srv)

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
		if w.Code != http.StatusBadGateway && w.Code != http.StatusInternalServerError {
			t.Errorf("endpoint %s %s returned %d, expected 502/500 on upstream error", ep.method, ep.path, w.Code)
		}
	}
}

func TestHandlers_NilStoreReturnsFallback(t *testing.T) {
	srv := &Server{Store: nil}
	r := setupTestRouterWithServer(srv)

	endpoints := []struct {
		method string
		path   string
	}{
		{http.MethodGet, "/api/holdings?user_id=usr_test"},
		{http.MethodGet, "/api/spending_report?user_id=usr_test"},
		{http.MethodGet, "/api/drift_report?user_id=usr_test"},
		{http.MethodGet, "/api/documents?user_id=usr_test"},
		{http.MethodGet, "/api/profile?user_id=usr_test"},
		{http.MethodGet, "/api/profile/w2?user_id=usr_test"},
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

func createW2MultipartUpload(filename, userID string, content []byte) (*http.Request, error) {
	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)
	if userID != "" {
		_ = writer.WriteField("user_id", userID)
	}
	part, err := writer.CreateFormFile("file", filename)
	if err != nil {
		return nil, err
	}
	if _, err := part.Write(content); err != nil {
		return nil, err
	}
	if err := writer.Close(); err != nil {
		return nil, err
	}

	req, err := http.NewRequest(http.MethodPost, "/api/profile/w2/upload", body)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())
	return req, nil
}

func TestW2Handlers_EndToEnd(t *testing.T) {
	mock := newMockStore()
	mockParser := documentai.NewMockW2Parser()
	srv := &Server{
		Store:       mock,
		DocAIParser: mockParser,
	}
	r := setupTestRouterWithServer(srv)

	// 1. Upload valid W-2 PDF
	req, err := createW2MultipartUpload("w2_2024.pdf", "user_abc", []byte("%PDF-1.4 test document"))
	if err != nil {
		t.Fatalf("failed to create upload request: %v", err)
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200 OK for W-2 upload, got %d: %s", w.Code, w.Body.String())
	}

	var uploadedDoc contracts.W2Document
	if err := json.Unmarshal(w.Body.Bytes(), &uploadedDoc); err != nil {
		t.Fatalf("failed to parse upload response: %v", err)
	}
	if uploadedDoc.UserID != "user_abc" || uploadedDoc.TaxYear != 2024 {
		t.Errorf("unexpected doc metadata: %+v", uploadedDoc)
	}
	if uploadedDoc.WagesAndCompensation.Box1WagesTipsOtherCompUSD != 220000.0 {
		t.Errorf("unexpected Box 1 wages: %v", uploadedDoc.WagesAndCompensation.Box1WagesTipsOtherCompUSD)
	}

	// 2. Query W-2 documents for user
	getReq, _ := http.NewRequest(http.MethodGet, "/api/profile/w2?user_id=user_abc", nil)
	getW := httptest.NewRecorder()
	r.ServeHTTP(getW, getReq)

	if getW.Code != http.StatusOK {
		t.Fatalf("expected 200 OK for get W-2s, got %d", getW.Code)
	}
	var docList []contracts.W2Document
	if err := json.Unmarshal(getW.Body.Bytes(), &docList); err != nil {
		t.Fatalf("failed to unmarshal W-2 list: %v", err)
	}
	if len(docList) != 1 || docList[0].ID != uploadedDoc.ID {
		t.Fatalf("expected 1 document with ID %s, got %d documents", uploadedDoc.ID, len(docList))
	}

	// 3. Apply W-2 to Profile
	applyReq, _ := http.NewRequest(http.MethodPost, fmt.Sprintf("/api/profile/w2/%s/apply?user_id=user_abc", uploadedDoc.ID), nil)
	applyW := httptest.NewRecorder()
	r.ServeHTTP(applyW, applyReq)

	if applyW.Code != http.StatusOK {
		t.Fatalf("expected 200 OK for apply W-2, got %d: %s", applyW.Code, applyW.Body.String())
	}

	profileReq, _ := http.NewRequest(http.MethodGet, "/api/profile?user_id=user_abc", nil)
	profileW := httptest.NewRecorder()
	r.ServeHTTP(profileW, profileReq)
	var updatedProfile contracts.UserProfile
	if err := json.Unmarshal(profileW.Body.Bytes(), &updatedProfile); err != nil {
		t.Fatalf("failed to parse profile response: %v", err)
	}
	if updatedProfile.AnnualIncomeUSD != 220000.0 {
		t.Errorf("expected AnnualIncomeUSD = 220000, got %v", updatedProfile.AnnualIncomeUSD)
	}

	// 4. Delete W-2 document
	delReq, _ := http.NewRequest(http.MethodDelete, fmt.Sprintf("/api/profile/w2/%s?user_id=user_abc", uploadedDoc.ID), nil)
	delW := httptest.NewRecorder()
	r.ServeHTTP(delW, delReq)

	if delW.Code != http.StatusOK {
		t.Fatalf("expected 200 OK for delete W-2, got %d", delW.Code)
	}

	// Verify deleted
	getReq2, _ := http.NewRequest(http.MethodGet, "/api/profile/w2?user_id=user_abc", nil)
	getW2 := httptest.NewRecorder()
	r.ServeHTTP(getW2, getReq2)
	var docList2 []contracts.W2Document
	_ = json.Unmarshal(getW2.Body.Bytes(), &docList2)
	if len(docList2) != 0 {
		t.Errorf("expected 0 documents after delete, got %d", len(docList2))
	}
}

func TestW2Handlers_ValidationErrors(t *testing.T) {
	mock := newMockStore()
	mockParser := documentai.NewMockW2Parser()
	srv := &Server{
		Store:       mock,
		DocAIParser: mockParser,
	}
	r := setupTestRouterWithServer(srv)

	// Unsupported extension (.txt)
	req1, _ := createW2MultipartUpload("w2.txt", "user1", []byte("hello"))
	w1 := httptest.NewRecorder()
	r.ServeHTTP(w1, req1)
	if w1.Code != http.StatusBadRequest {
		t.Errorf("expected 400 Bad Request for .txt file, got %d", w1.Code)
	}

	// Delete non-existent ID
	delReq, _ := http.NewRequest(http.MethodDelete, "/api/profile/w2/non-existent-id?user_id=user1", nil)
	delW := httptest.NewRecorder()
	r.ServeHTTP(delW, delReq)
	if delW.Code != http.StatusNotFound {
		t.Errorf("expected 404 Not Found for deleting non-existent W-2, got %d", delW.Code)
	}

	// Apply non-existent ID
	applyReq, _ := http.NewRequest(http.MethodPost, "/api/profile/w2/non-existent-id/apply?user_id=user1", nil)
	applyW := httptest.NewRecorder()
	r.ServeHTTP(applyW, applyReq)
	if applyW.Code != http.StatusNotFound {
		t.Errorf("expected 404 Not Found for applying non-existent W-2, got %d", applyW.Code)
	}
}


