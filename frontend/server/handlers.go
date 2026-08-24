package main

import (
	"context"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"

	cloudbigquery "cloud.google.com/go/bigquery"
	"github.com/gin-gonic/gin"
	"portfolio-copilot/pkg/bigquery"
	"portfolio-copilot/pkg/contracts"
	"portfolio-copilot/pkg/documentai"
	"portfolio-copilot/pkg/store"
)

var validUserIDRegex = regexp.MustCompile(`^[a-zA-Z0-9_-]{1,64}$`)

func validateUserID(userID string) (string, error) {
	trimmed := strings.TrimSpace(userID)
	if trimmed == "" || !validUserIDRegex.MatchString(trimmed) {
		return "", fmt.Errorf("invalid user_id format: %q", userID)
	}
	return trimmed, nil
}

// Server holds dependencies for HTTP handlers, using interfaces for testability.
type Server struct {
	Store       store.Store
	BQRunner    bigquery.Runner
	DocAIParser documentai.Parser
}

// NewServer initializes a Server, attempting to connect to Firestore, BigQuery, and Document AI if configured.
func NewServer() *Server {
	ctx := context.Background()
	projectID := os.Getenv("FIRESTORE_PROJECT_ID")
	if projectID == "" {
		projectID = os.Getenv("GOOGLE_CLOUD_PROJECT")
	}
	if projectID == "" {
		projectID = os.Getenv("PROJECT_ID")
	}
	var storeClient store.Store
	var bqRunner bigquery.Runner
	var docAIParser documentai.Parser

	if projectID != "" {
		// store.NewClient reads PROJECT_ID from the environment; set it once at server initialization
		// if not already present.
		if os.Getenv("PROJECT_ID") == "" {
			os.Setenv("PROJECT_ID", projectID)
		}
		client, err := store.NewClient(ctx)
		if err != nil {
			slog.Warn("Failed to initialize Firestore store client; using fallback mode", "error", err)
		} else {
			storeClient = client
			slog.Info("Connected to Firestore store client", "project_id", projectID)
		}

		bqClient, err := cloudbigquery.NewClient(ctx, projectID)
		if err != nil {
			slog.Warn("Failed to initialize BigQuery client; transactions will not stream to BigQuery", "error", err)
		} else {
			bqRunner = bigquery.NewBigQueryRunner(bqClient)
			slog.Info("Connected to BigQuery client", "project_id", projectID)
		}
	} else {
		slog.Info("No PROJECT_ID set; server running in fallback mode")
	}

	docAIProcessorID := os.Getenv("DOCUMENT_AI_PROCESSOR_ID")
	docAILocation := os.Getenv("DOCUMENT_AI_LOCATION")
	if docAILocation == "" {
		docAILocation = "us"
	}
	docAIProjectID := os.Getenv("DOCUMENT_AI_PROJECT_ID")
	if docAIProjectID == "" {
		docAIProjectID = projectID
	}

	if docAIProcessorID != "" && docAIProjectID != "" {
		gcpParser, err := documentai.NewGCPW2Parser(ctx, docAIProjectID, docAILocation, docAIProcessorID)
		if err != nil {
			slog.Warn("Failed to initialize GCP Document AI client; falling back to MockW2Parser", "error", err)
			docAIParser = documentai.NewMockW2Parser()
		} else {
			docAIParser = gcpParser
			slog.Info("Connected to GCP Document AI client", "project_id", docAIProjectID, "processor_id", docAIProcessorID)
		}
	} else {
		slog.Info("No DOCUMENT_AI_PROCESSOR_ID configured; using MockW2Parser for dev/test")
		docAIParser = documentai.NewMockW2Parser()
	}

	return &Server{
		Store:       storeClient,
		BQRunner:    bqRunner,
		DocAIParser: docAIParser,
	}
}

// Close gracefully closes external client connections held by Server.
func (s *Server) Close() error {
	var errs []string
	if closer, ok := s.DocAIParser.(io.Closer); ok && closer != nil {
		if err := closer.Close(); err != nil {
			errs = append(errs, fmt.Sprintf("docai: %v", err))
		}
	}
	if closer, ok := s.Store.(io.Closer); ok && closer != nil {
		if err := closer.Close(); err != nil {
			errs = append(errs, fmt.Sprintf("store: %v", err))
		}
	}
	if len(errs) > 0 {
		return fmt.Errorf("server close errors: %s", strings.Join(errs, "; "))
	}
	return nil
}

func (s *Server) HandleGetHoldings(c *gin.Context) {
	userID, err := validateUserID(c.DefaultQuery("user_id", "demo_user"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid user_id parameter"})
		return
	}
	if s.Store == nil {
		c.JSON(http.StatusOK, defaultHoldings())
		return
	}
	snapshot, err := s.Store.GetHoldings(c.Request.Context(), userID)
	switch {
	case err == nil && snapshot != nil:
		c.JSON(http.StatusOK, snapshot)
	case store.IsNotFound(err):
		c.JSON(http.StatusOK, defaultHoldings())
	default:
		slog.ErrorContext(c.Request.Context(), "Error reading holdings from Firestore", "user_id", userID, "error", err)
		c.JSON(http.StatusBadGateway, gin.H{"error": "upstream data unavailable"})
	}
}

func (s *Server) HandleGetSpendingReport(c *gin.Context) {
	userID, err := validateUserID(c.DefaultQuery("user_id", "demo_user"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid user_id parameter"})
		return
	}
	if s.Store == nil {
		c.JSON(http.StatusOK, defaultSpendingReport())
		return
	}
	report, err := s.Store.GetSpendingReport(c.Request.Context(), userID)
	switch {
	case err == nil && report != nil:
		c.JSON(http.StatusOK, report)
	case store.IsNotFound(err):
		c.JSON(http.StatusOK, defaultSpendingReport())
	default:
		slog.ErrorContext(c.Request.Context(), "Error reading spending report from Firestore", "user_id", userID, "error", err)
		c.JSON(http.StatusBadGateway, gin.H{"error": "upstream data unavailable"})
	}
}

func (s *Server) HandleGetDriftReport(c *gin.Context) {
	userID, err := validateUserID(c.DefaultQuery("user_id", "demo_user"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid user_id parameter"})
		return
	}
	if s.Store == nil {
		c.JSON(http.StatusOK, defaultDriftReport())
		return
	}
	report, err := s.Store.GetDriftReport(c.Request.Context(), userID)
	switch {
	case err == nil && report != nil:
		c.JSON(http.StatusOK, report)
	case store.IsNotFound(err):
		c.JSON(http.StatusOK, defaultDriftReport())
	default:
		slog.ErrorContext(c.Request.Context(), "Error reading drift report from Firestore", "user_id", userID, "error", err)
		c.JSON(http.StatusBadGateway, gin.H{"error": "upstream data unavailable"})
	}
}

func (s *Server) HandleGetDocuments(c *gin.Context) {
	userID, err := validateUserID(c.DefaultQuery("user_id", "demo_user"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid user_id parameter"})
		return
	}
	if s.Store == nil {
		c.JSON(http.StatusOK, defaultDocuments())
		return
	}
	items, err := s.Store.GetDocuments(c.Request.Context(), userID)
	switch {
	case err == nil:
		if len(items) == 0 {
			c.JSON(http.StatusOK, defaultDocuments())
		} else {
			c.JSON(http.StatusOK, items)
		}
	case store.IsNotFound(err):
		c.JSON(http.StatusOK, defaultDocuments())
	default:
		slog.ErrorContext(c.Request.Context(), "Error reading documents from Firestore", "user_id", userID, "error", err)
		c.JSON(http.StatusBadGateway, gin.H{"error": "upstream data unavailable"})
	}
}

func (s *Server) HandleGetUserProfile(c *gin.Context) {
	userID, err := validateUserID(c.DefaultQuery("user_id", "demo_user"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid user_id parameter"})
		return
	}
	if s.Store == nil {
		c.JSON(http.StatusOK, defaultUserProfile())
		return
	}
	profile, err := s.Store.GetUserProfile(c.Request.Context(), userID)
	switch {
	case err == nil && profile != nil:
		c.JSON(http.StatusOK, profile)
	case store.IsNotFound(err):
		c.JSON(http.StatusOK, defaultUserProfile())
	default:
		slog.ErrorContext(c.Request.Context(), "Error reading user profile from Firestore", "user_id", userID, "error", err)
		c.JSON(http.StatusBadGateway, gin.H{"error": "upstream data unavailable"})
	}
}

func (s *Server) HandleSetUserProfile(c *gin.Context) {
	var profile contracts.UserProfile
	if err := c.ShouldBindJSON(&profile); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("invalid payload: %v", err)})
		return
	}
	if profile.UserID == "" {
		profile.UserID = "demo_user"
	}
	if _, err := validateUserID(profile.UserID); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid user_id parameter"})
		return
	}
	profile.UpdatedAt = time.Now().UTC().Format(time.RFC3339)

	if s.Store == nil {
		c.JSON(http.StatusOK, gin.H{"status": "ok", "profile": profile})
		return
	}

	if err := s.Store.SetUserProfile(c.Request.Context(), profile.UserID, &profile); err != nil {
		slog.ErrorContext(c.Request.Context(), "Error saving user profile to Firestore", "user_id", profile.UserID, "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to persist profile"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "ok", "profile": profile})
}

func (s *Server) HandleGetOnboarding(c *gin.Context) {
	userID, err := validateUserID(c.DefaultQuery("user_id", "demo_user"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid user_id parameter"})
		return
	}
	if s.Store == nil {
		c.JSON(http.StatusOK, contracts.OnboardingProfile{
			HasActiveIPS: false,
			UserID:       userID,
		})
		return
	}

	ips, ipsErr := s.Store.GetActiveIPS(c.Request.Context(), userID)
	if ipsErr != nil && !store.IsNotFound(ipsErr) {
		slog.ErrorContext(c.Request.Context(), "Error reading active IPS from Firestore", "user_id", userID, "error", ipsErr)
		c.JSON(http.StatusBadGateway, gin.H{"error": "upstream data unavailable"})
		return
	}

	if store.IsNotFound(ipsErr) || ips == nil {
		c.JSON(http.StatusOK, contracts.OnboardingProfile{
			HasActiveIPS: false,
			UserID:       userID,
		})
		return
	}

	liabSnapshot, liabErr := s.Store.GetLiabilities(c.Request.Context(), userID)
	var liabilities []contracts.Liability
	if liabErr == nil && liabSnapshot != nil {
		liabilities = liabSnapshot.Liabilities
	}

	var upcomingExpenses float64
	var reserveMonths float64
	if ips.LiquidityNeeds != nil {
		if ips.LiquidityNeeds.KnownUpcomingExpensesUSD != nil {
			upcomingExpenses = *ips.LiquidityNeeds.KnownUpcomingExpensesUSD
		}
		if ips.LiquidityNeeds.ReserveMonths != nil {
			reserveMonths = *ips.LiquidityNeeds.ReserveMonths
		}
	}

	var approvalUSD float64
	var approvalPct float64
	if ips.ApprovalRequiredAboveUSD != nil {
		approvalUSD = *ips.ApprovalRequiredAboveUSD
	}
	if ips.ApprovalRequiredAbovePercent != nil {
		approvalPct = *ips.ApprovalRequiredAbovePercent
	}

	var constraints *contracts.Constraints
	if ips.Constraints.ConcentrationLimitPercent > 0 || len(ips.Constraints.ExcludedTickers) > 0 || len(ips.Constraints.ExcludedSectors) > 0 {
		c := ips.Constraints
		constraints = &c
	}

	profile := contracts.OnboardingProfile{
		HasActiveIPS:                 true,
		UserID:                       ips.UserID,
		IPSID:                        ips.IPSID,
		Version:                      ips.Version,
		Goals:                        ips.Goals,
		TimeHorizonYears:             ips.TimeHorizonYears,
		KnownUpcomingExpensesUSD:     upcomingExpenses,
		ReserveMonths:                reserveMonths,
		RiskTolerance:                ips.RiskTolerance,
		TargetBands:                  ips.TargetAllocation,
		Constraints:                  constraints,
		ApprovalRequiredAboveUSD:     approvalUSD,
		ApprovalRequiredAbovePercent: approvalPct,
		Liabilities:                  liabilities,
	}

	c.JSON(http.StatusOK, profile)
}

func (s *Server) HandleUploadDocument(c *gin.Context) {
	userID, err := validateUserID(c.DefaultPostForm("user_id", "demo_user"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid user_id parameter"})
		return
	}
	documentType := strings.ToLower(strings.TrimSpace(c.PostForm("document_type")))
	targetTable := strings.TrimSpace(c.PostForm("target_table"))

	if s.Store == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error": "document ingestion unavailable: storage backend is not connected",
		})
		return
	}

	if documentType == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "document_type is required (transactions, holdings, liabilities, ips)"})
		return
	}

	allowedTypes := map[string]bool{
		"transactions": true,
		"holdings":     true,
		"liabilities":  true,
		"ips":          true,
	}
	if !allowedTypes[documentType] {
		c.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("unsupported document_type '%s'; accepted types: transactions, holdings, liabilities, ips", documentType)})
		return
	}

	fileHeader, err := c.FormFile("file")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("file is required: %v", err)})
		return
	}

	if fileHeader.Size > (10 << 20) {
		c.JSON(http.StatusBadRequest, gin.H{"error": "file exceeds maximum allowed size of 10MB"})
		return
	}

	ext := strings.ToLower(filepath.Ext(fileHeader.Filename))
	var expectedExt string
	switch documentType {
	case "transactions":
		expectedExt = ".csv"
	case "holdings", "liabilities", "ips":
		expectedExt = ".json"
	}

	if ext != expectedExt {
		c.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("invalid file extension '%s' for document_type '%s'; expected '%s'", ext, documentType, expectedExt)})
		return
	}

	file, err := fileHeader.Open()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to open uploaded file: %v", err)})
		return
	}
	defer file.Close()

	fileBytes, err := io.ReadAll(file)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to read uploaded file: %v", err)})
		return
	}

	docID := fmt.Sprintf("doc-%d", time.Now().UnixNano())
	docItem := contracts.DocumentItem{
		ID:           docID,
		UserID:       userID,
		Filename:     fileHeader.Filename,
		DocumentType: documentType,
		AccountType:  documentType,
		TargetTable:  targetTable,
		SizeBytes:    fileHeader.Size,
		UploadedAt:   time.Now().UTC().Format(time.RFC3339),
		Status:       "SUCCESS",
	}

	var recordsParsed int
	ctx := c.Request.Context()

	switch documentType {
	case "transactions":
		if s.BQRunner == nil {
			errMsg := "transactions ingestion unavailable: BigQuery is not connected"
			docItem.Status = "FAILED"
			docItem.ErrorMessage = &errMsg
			_ = s.Store.SetDocument(ctx, &docItem)
			c.JSON(http.StatusServiceUnavailable, gin.H{"error": errMsg, "document": docItem})
			return
		}

		if docItem.TargetTable == "" {
			docItem.TargetTable = "checking_transactions"
		}
		if docItem.TargetTable != "checking_transactions" {
			errMsg := fmt.Sprintf("invalid target_table: %s (must be checking_transactions)", docItem.TargetTable)
			docItem.Status = "FAILED"
			docItem.ErrorMessage = &errMsg
			_ = s.Store.SetDocument(ctx, &docItem)
			c.JSON(http.StatusBadRequest, gin.H{"error": errMsg, "document": docItem})
			return
		}

		reader := csv.NewReader(strings.NewReader(string(fileBytes)))
		records, err := reader.ReadAll()
		if err != nil || len(records) < 2 {
			errMsg := "invalid CSV: must contain header and at least 1 data row"
			if err != nil {
				errMsg = fmt.Sprintf("CSV parse error: %v", err)
			}
			docItem.Status = "FAILED"
			docItem.ErrorMessage = &errMsg
			_ = s.Store.SetDocument(ctx, &docItem)
			c.JSON(http.StatusBadRequest, gin.H{"error": errMsg, "document": docItem})
			return
		}

		// Validate header columns and order against canonical schema
		expectedHeaders := []string{"user_id", "transaction_date", "amount", "description", "raw_category", "normalized_category"}
		header := records[0]
		if len(header) != len(expectedHeaders) {
			errMsg := fmt.Sprintf("invalid CSV header: expected %d columns (%s), got %d", len(expectedHeaders), strings.Join(expectedHeaders, ", "), len(header))
			docItem.Status = "FAILED"
			docItem.ErrorMessage = &errMsg
			_ = s.Store.SetDocument(ctx, &docItem)
			c.JSON(http.StatusBadRequest, gin.H{"error": errMsg, "document": docItem})
			return
		}
		for i, expected := range expectedHeaders {
			actual := strings.TrimSpace(strings.ToLower(header[i]))
			if actual != expected {
				errMsg := fmt.Sprintf("invalid CSV header at column %d: expected %q, got %q", i+1, expected, header[i])
				docItem.Status = "FAILED"
				docItem.ErrorMessage = &errMsg
				_ = s.Store.SetDocument(ctx, &docItem)
				c.JSON(http.StatusBadRequest, gin.H{"error": errMsg, "document": docItem})
				return
			}
		}

		var txRecords []bigquery.TransactionRecord
		for i, row := range records[1:] {
			rowNum := i + 2
			if len(row) != len(expectedHeaders) {
				errMsg := fmt.Sprintf("row %d: expected %d columns, got %d", rowNum, len(expectedHeaders), len(row))
				docItem.Status = "FAILED"
				docItem.ErrorMessage = &errMsg
				_ = s.Store.SetDocument(ctx, &docItem)
				c.JSON(http.StatusBadRequest, gin.H{"error": errMsg, "document": docItem})
				return
			}

			txDate := strings.TrimSpace(row[1])
			if _, err := time.Parse("2006-01-02", txDate); err != nil {
				errMsg := fmt.Sprintf("row %d: invalid transaction_date '%s' (expected YYYY-MM-DD)", rowNum, txDate)
				docItem.Status = "FAILED"
				docItem.ErrorMessage = &errMsg
				_ = s.Store.SetDocument(ctx, &docItem)
				c.JSON(http.StatusBadRequest, gin.H{"error": errMsg, "document": docItem})
				return
			}

			amtStr := strings.TrimSpace(row[2])
			amt, err := strconv.ParseFloat(amtStr, 64)
			if err != nil {
				errMsg := fmt.Sprintf("row %d: invalid amount '%s'", rowNum, amtStr)
				docItem.Status = "FAILED"
				docItem.ErrorMessage = &errMsg
				_ = s.Store.SetDocument(ctx, &docItem)
				c.JSON(http.StatusBadRequest, gin.H{"error": errMsg, "document": docItem})
				return
			}

			normCat := strings.TrimSpace(row[5])
			if normCat == "" {
				errMsg := fmt.Sprintf("row %d: normalized_category cannot be empty", rowNum)
				docItem.Status = "FAILED"
				docItem.ErrorMessage = &errMsg
				_ = s.Store.SetDocument(ctx, &docItem)
				c.JSON(http.StatusBadRequest, gin.H{"error": errMsg, "document": docItem})
				return
			}

			txRecords = append(txRecords, bigquery.TransactionRecord{
				UserID:             userID, // Force scope to authenticated request identity
				TransactionDate:    txDate,
				Amount:             amt,
				Description:        strings.TrimSpace(row[3]),
				RawCategory:        strings.TrimSpace(row[4]),
				NormalizedCategory: normCat,
			})
		}

		dataset := os.Getenv("BIGQUERY_DATASET")
		if dataset == "" {
			dataset = "portfolio_copilot"
		}
		if err := s.BQRunner.InsertTransactions(ctx, dataset, docItem.TargetTable, txRecords); err != nil {
			errMsg := fmt.Sprintf("failed to insert transactions into BigQuery: %v", err)
			docItem.Status = "FAILED"
			docItem.ErrorMessage = &errMsg
			_ = s.Store.SetDocument(ctx, &docItem)
			c.JSON(http.StatusBadRequest, gin.H{"error": errMsg, "document": docItem})
			return
		}

		recordsParsed = len(txRecords)

	case "holdings":
		var snapshot contracts.HoldingsSnapshot
		if err := json.Unmarshal(fileBytes, &snapshot); err != nil {
			errMsg := fmt.Sprintf("JSON parse error for holdings: %v", err)
			docItem.Status = "FAILED"
			docItem.ErrorMessage = &errMsg
			_ = s.Store.SetDocument(ctx, &docItem)
			c.JSON(http.StatusBadRequest, gin.H{"error": errMsg, "document": docItem})
			return
		}
		// Force request identity
		snapshot.UserID = userID
		recordsParsed = len(snapshot.Positions)
		if err := s.Store.SetHoldings(ctx, userID, &snapshot); err != nil {
			errMsg := fmt.Sprintf("failed to persist holdings: %v", err)
			docItem.Status = "FAILED"
			docItem.ErrorMessage = &errMsg
			_ = s.Store.SetDocument(ctx, &docItem)
			c.JSON(http.StatusBadRequest, gin.H{"error": errMsg, "document": docItem})
			return
		}

	case "liabilities":
		var snapshot contracts.LiabilitiesSnapshot
		if err := json.Unmarshal(fileBytes, &snapshot); err != nil {
			errMsg := fmt.Sprintf("JSON parse error for liabilities: %v", err)
			docItem.Status = "FAILED"
			docItem.ErrorMessage = &errMsg
			_ = s.Store.SetDocument(ctx, &docItem)
			c.JSON(http.StatusBadRequest, gin.H{"error": errMsg, "document": docItem})
			return
		}
		// Force request identity
		snapshot.UserID = userID
		recordsParsed = len(snapshot.Liabilities)
		if err := s.Store.SetLiabilities(ctx, userID, &snapshot); err != nil {
			errMsg := fmt.Sprintf("failed to persist liabilities: %v", err)
			docItem.Status = "FAILED"
			docItem.ErrorMessage = &errMsg
			_ = s.Store.SetDocument(ctx, &docItem)
			c.JSON(http.StatusBadRequest, gin.H{"error": errMsg, "document": docItem})
			return
		}

	case "ips":
		var ips contracts.InvestmentPolicyStatement
		if err := json.Unmarshal(fileBytes, &ips); err != nil {
			errMsg := fmt.Sprintf("JSON parse error for IPS: %v", err)
			docItem.Status = "FAILED"
			docItem.ErrorMessage = &errMsg
			_ = s.Store.SetDocument(ctx, &docItem)
			c.JSON(http.StatusBadRequest, gin.H{"error": errMsg, "document": docItem})
			return
		}
		// Force request identity
		ips.UserID = userID
		// Integrity floor (SEC-04, #355): reject a defanged-but-schema-valid IPS
		// here too, so a direct upload can't install a policy that neuters the
		// deterministic reviewer. Mirrors the orchestrator's Pydantic validators.
		if err := ips.ValidateIntegrity(); err != nil {
			errMsg := fmt.Sprintf("IPS integrity validation failed: %v", err)
			docItem.Status = "FAILED"
			docItem.ErrorMessage = &errMsg
			_ = s.Store.SetDocument(ctx, &docItem)
			c.JSON(http.StatusBadRequest, gin.H{"error": errMsg, "document": docItem})
			return
		}
		recordsParsed = 1
		if err := s.Store.UpdateIPS(ctx, &ips); err != nil {
			errMsg := fmt.Sprintf("failed to update IPS: %v", err)
			docItem.Status = "FAILED"
			docItem.ErrorMessage = &errMsg
			_ = s.Store.SetDocument(ctx, &docItem)
			c.JSON(http.StatusBadRequest, gin.H{"error": errMsg, "document": docItem})
			return
		}
	}

	docItem.RecordsParsed = &recordsParsed
	if err := s.Store.SetDocument(ctx, &docItem); err != nil {
		slog.WarnContext(ctx, "Failed to record document metadata in store", "doc_id", docItem.ID, "error", err)
	}

	c.JSON(http.StatusOK, docItem)
}

func (s *Server) HandleUploadW2(c *gin.Context) {
	userID, err := validateUserID(c.DefaultPostForm("user_id", "demo_user"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid user_id parameter"})
		return
	}

	if s.DocAIParser == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "Document AI parsing is unavailable"})
		return
	}

	fileHeader, err := c.FormFile("file")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("file is required: %v", err)})
		return
	}

	if fileHeader.Size > (10 << 20) {
		c.JSON(http.StatusBadRequest, gin.H{"error": "file exceeds maximum allowed size of 10MB"})
		return
	}

	ext := strings.ToLower(filepath.Ext(fileHeader.Filename))
	var mimeType string
	switch ext {
	case ".pdf":
		mimeType = "application/pdf"
	case ".png":
		mimeType = "image/png"
	case ".jpg", ".jpeg":
		mimeType = "image/jpeg"
	default:
		c.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("unsupported file extension %q; expected .pdf, .png, or .jpg/.jpeg", ext)})
		return
	}

	file, err := fileHeader.Open()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to open uploaded file: %v", err)})
		return
	}
	defer file.Close()

	fileBytes, err := io.ReadAll(file)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to read uploaded file: %v", err)})
		return
	}

	ctx := c.Request.Context()
	w2Doc, err := s.DocAIParser.ParseW2(ctx, fileBytes, mimeType, fileHeader.Filename, userID)
	if err != nil {
		slog.ErrorContext(ctx, "Document AI W-2 extraction failed", "user_id", userID, "error", err)
		c.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("failed to extract W-2 data: %v", err)})
		return
	}

	w2Doc.UserID = userID
	w2Doc.Filename = fileHeader.Filename
	w2Doc.SizeBytes = fileHeader.Size

	if s.Store != nil {
		if err := s.Store.SetW2Document(ctx, w2Doc); err != nil {
			slog.ErrorContext(ctx, "Failed to persist W-2 document to Firestore", "doc_id", w2Doc.ID, "error", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to persist W-2 document"})
			return
		}

		docItem := contracts.DocumentItem{
			ID:           w2Doc.ID,
			UserID:       userID,
			Filename:     fileHeader.Filename,
			DocumentType: "w2",
			AccountType:  "tax",
			SizeBytes:    fileHeader.Size,
			UploadedAt:   w2Doc.UploadedAt,
			Status:       string(w2Doc.Status),
		}
		_ = s.Store.SetDocument(ctx, &docItem)
	}

	c.JSON(http.StatusOK, w2Doc)
}

func (s *Server) HandleGetW2Documents(c *gin.Context) {
	userID, err := validateUserID(c.DefaultQuery("user_id", "demo_user"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid user_id parameter"})
		return
	}
	if s.Store == nil {
		c.JSON(http.StatusOK, []contracts.W2Document{})
		return
	}
	docs, err := s.Store.GetW2Documents(c.Request.Context(), userID)
	if err != nil {
		slog.ErrorContext(c.Request.Context(), "Error reading W-2 documents from Firestore", "user_id", userID, "error", err)
		c.JSON(http.StatusBadGateway, gin.H{"error": "upstream data unavailable"})
		return
	}
	if docs == nil {
		docs = []contracts.W2Document{}
	}
	c.JSON(http.StatusOK, docs)
}

func (s *Server) HandleDeleteW2Document(c *gin.Context) {
	userID, err := validateUserID(c.DefaultQuery("user_id", "demo_user"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid user_id parameter"})
		return
	}
	docID := c.Param("id")
	if docID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "id parameter is required"})
		return
	}

	if s.Store == nil {
		if docID != "w2-demo-1" && !strings.HasPrefix(docID, "w2-") {
			c.JSON(http.StatusNotFound, gin.H{"error": "w2 document not found"})
			return
		}
		c.JSON(http.StatusOK, gin.H{"status": "deleted", "id": docID})
		return
	}

	if err := s.Store.DeleteW2Document(c.Request.Context(), userID, docID); err != nil {
		if store.IsNotFound(err) {
			c.JSON(http.StatusNotFound, gin.H{"error": "w2 document not found"})
			return
		}
		slog.ErrorContext(c.Request.Context(), "Error deleting W-2 document from Firestore", "user_id", userID, "doc_id", docID, "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to delete w2 document"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "deleted", "id": docID})
}

func (s *Server) HandleApplyW2ToProfile(c *gin.Context) {
	userID, err := validateUserID(c.DefaultQuery("user_id", "demo_user"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid user_id parameter"})
		return
	}
	docID := c.Param("id")
	if docID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "id parameter is required"})
		return
	}

	if s.Store == nil {
		if docID != "w2-demo-1" && !strings.HasPrefix(docID, "w2-") {
			c.JSON(http.StatusNotFound, gin.H{"error": "w2 document not found"})
			return
		}
		profile := defaultUserProfile()
		profile.AnnualIncomeUSD = 220000.0
		profile.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
		c.JSON(http.StatusOK, gin.H{"status": "applied", "profile": profile})
		return
	}

	ctx := c.Request.Context()
	w2, err := s.Store.GetW2Document(ctx, userID, docID)
	if err != nil {
		if store.IsNotFound(err) {
			c.JSON(http.StatusNotFound, gin.H{"error": "w2 document not found"})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to retrieve w2 document: %v", err)})
		return
	}

	profile, err := s.Store.GetUserProfile(ctx, userID)
	if err != nil {
		if store.IsNotFound(err) {
			profile = &contracts.UserProfile{
				UserID:   userID,
				FullName: userID,
			}
		} else {
			slog.ErrorContext(ctx, "Failed to retrieve user profile for W-2 apply", "user_id", userID, "error", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to retrieve user profile"})
			return
		}
	} else if profile == nil {
		profile = &contracts.UserProfile{
			UserID:   userID,
			FullName: userID,
		}
	}

	profile.AnnualIncomeUSD = w2.WagesAndCompensation.Box1WagesTipsOtherCompUSD
	if w2.Employer != nil && w2.Employer.Name != "" && profile.Occupation == "" {
		profile.Occupation = fmt.Sprintf("Employee at %s", w2.Employer.Name)
	}
	profile.UpdatedAt = time.Now().UTC().Format(time.RFC3339)

	if err := s.Store.SetUserProfile(ctx, userID, profile); err != nil {
		slog.ErrorContext(ctx, "Failed to update user profile with W-2 income", "user_id", userID, "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to persist updated profile"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "applied", "profile": profile})
}

func ptrInt(i int) *int {
	return &i
}

func ptrFloat64(f float64) *float64 {
	return &f
}

func defaultHoldings() *contracts.HoldingsSnapshot {
	now := time.Now().UTC()
	return &contracts.HoldingsSnapshot{
		UserID:        "demo_user",
		TotalValueUSD: ptrFloat64(200000.0),
		CashUSD:       ptrFloat64(20000.0),
		AsOf:          now,
		Positions: []contracts.Position{
			{
				Ticker:         "VTI",
				Name:           "Vanguard Total Stock Market ETF",
				Quantity:       400,
				AssetClass:     "Equity",
				MarketValueUSD: 110000.0,
			},
			{
				Ticker:         "AAPL",
				Name:           "Apple Inc.",
				Quantity:       100,
				AssetClass:     "Equity",
				MarketValueUSD: 25000.0,
			},
			{
				Ticker:         "BND",
				Name:           "Vanguard Total Bond Market ETF",
				Quantity:       400,
				AssetClass:     "Bonds",
				MarketValueUSD: 35000.0,
			},
			{
				Ticker:         "BTC",
				Name:           "Bitcoin",
				Quantity:       0.15,
				AssetClass:     "Crypto",
				MarketValueUSD: 10000.0,
			},
		},
	}
}

func defaultSpendingReport() *contracts.SpendingReport {
	return &contracts.SpendingReport{
		UserID:          "demo_user",
		TotalIncomeUSD:  18500.0,
		TotalOutflowUSD: 13227.5,
		SavingsRate:     0.285,
		ReserveMonths:   8.2,
		CategoryBreakdown: []contracts.CategorySpending{
			{Category: "housing", AmountUSD: 4200.0, PercentOfTotal: 31.8},
			{Category: "dining", AmountUSD: 2150.0, PercentOfTotal: 16.3},
			{Category: "groceries", AmountUSD: 1680.0, PercentOfTotal: 12.7},
			{Category: "transportation", AmountUSD: 1240.0, PercentOfTotal: 9.4},
			{Category: "utilities", AmountUSD: 620.0, PercentOfTotal: 4.7},
			{Category: "other", AmountUSD: 3337.5, PercentOfTotal: 25.1},
		},
		Anomalies: []contracts.SpendingAnomaly{
			{
				Category:           "dining",
				AmountUSD:          2150.0,
				TrailingAverageUSD: 1350.0,
				Description:        "Dining spend jumped 59% above trailing 3-month average ($1,350/mo)",
				Date:               "2023-10-15",
			},
		},
		NarrativeSummary: "Spending is well-controlled with a healthy 28.5% savings rate and 8.2 months of cash liquidity. However, dining expenditures exceeded trailing averages by $800 this month.",
	}
}

func defaultDriftReport() *contracts.DriftReport {
	return &contracts.DriftReport{
		// Fixed date so snapshot / equality tests aren't time-dependent.
		// This is dev-mode fallback data anyway; the real drift report comes
		// from Firestore with its own timestamp.
		AsOf:                 "2026-01-01",
		HasActiveIPS:         true,
		RebalanceRecommended: true,
		UnclassifiedValueUSD: 0.0,
		Bands: []contracts.DriftBandItem{
			{
				AssetClass:         "Equities (US)",
				CurrentPercent:     58.4,
				TargetPercent:      55.0,
				MinPercent:         50.0,
				MaxPercent:         58.0,
				InBand:             false,
				DriftAmountPercent: 3.4,
			},
			{
				AssetClass:         "Equities (Intl)",
				CurrentPercent:     23.6,
				TargetPercent:      25.0,
				MinPercent:         20.0,
				MaxPercent:         30.0,
				InBand:             true,
				DriftAmountPercent: 0.0,
			},
			{
				AssetClass:         "Fixed Income",
				CurrentPercent:     13.0,
				TargetPercent:      15.0,
				MinPercent:         10.0,
				MaxPercent:         20.0,
				InBand:             true,
				DriftAmountPercent: 0.0,
			},
			{
				AssetClass:         "Cash/Equiv",
				CurrentPercent:     5.0,
				TargetPercent:      5.0,
				MinPercent:         2.0,
				MaxPercent:         10.0,
				InBand:             true,
				DriftAmountPercent: 0.0,
			},
		},
	}
}

func defaultDocuments() []contracts.DocumentItem {
	return []contracts.DocumentItem{
		{
			ID:            "doc-1",
			Filename:      "Checking_Stmt_Oct2023.csv",
			AccountType:   "checking",
			TargetTable:   "checking_transactions",
			SizeBytes:     1258291,
			UploadedAt:    "2023-10-24T09:41:00Z",
			Status:        "SUCCESS",
			RecordsParsed: ptrInt(36),
		},
	}
}

func defaultUserProfile() *contracts.UserProfile {
	return &contracts.UserProfile{
		UserID:                  "demo_user",
		FullName:                "Alex Mercer",
		Email:                   "alex.mercer@example.com",
		DateOfBirth:             "1980-06-15",
		Age:                     46,
		MaritalStatus:           "married",
		DependentsCount:         2,
		FamilyMembers: []contracts.FamilyMember{
			{Name: "Sarah Mercer", Relationship: "spouse", Age: 44},
			{Name: "Leo Mercer", Relationship: "child", Age: 12},
			{Name: "Maya Mercer", Relationship: "child", Age: 9},
		},
		EmploymentStatus:        "employed",
		Occupation:              "Staff Systems Engineer",
		AnnualIncomeUSD:         220000.0,
		TargetRetirementAge:     61,
		MonthlyHousingPaymentUSD: 4200.0,
		RiskToleranceNotes:      "Comfortable with moderate volatility in pursuit of long-term capital appreciation; prefers broad-market index funds.",
		FinancialGoalsNotes:     "Build a $1.5M nest egg for retirement by 2041 and maintain 6 months of liquid emergency reserves.",
		UpdatedAt:               "2026-08-01T00:00:00Z",
	}
}

func ptrString(s string) *string {
	return &s
}
