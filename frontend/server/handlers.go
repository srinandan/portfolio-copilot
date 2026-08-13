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
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"portfolio-copilot/pkg/contracts"
	"portfolio-copilot/pkg/store"
)

// Server holds dependencies for HTTP handlers, including the Firestore store client.
type Server struct {
	Store *store.Client
}

// NewServer initializes a Server, attempting to connect to Firestore if configured.
func NewServer() *Server {
	ctx := context.Background()
	projectID := os.Getenv("FIRESTORE_PROJECT_ID")
	if projectID == "" {
		projectID = os.Getenv("GOOGLE_CLOUD_PROJECT")
	}
	if projectID == "" {
		projectID = os.Getenv("PROJECT_ID")
	}
	var storeClient *store.Client
	if projectID != "" {
		// store.NewClient reads PROJECT_ID from the environment; set it once at server initialization
		// if not already present.
		if os.Getenv("PROJECT_ID") == "" {
			os.Setenv("PROJECT_ID", projectID)
		}
		var err error
		storeClient, err = store.NewClient(ctx)
		if err != nil {
			slog.Warn("Failed to initialize Firestore store client; using fallback mode", "error", err)
		} else {
			slog.Info("Connected to Firestore store client", "project_id", projectID)
		}
	} else {
		slog.Info("No PROJECT_ID set; server running in fallback mode")
	}
	return &Server{
		Store: storeClient,
	}
}

func (s *Server) HandleGetHoldings(c *gin.Context) {
	userID := c.DefaultQuery("user_id", "demo_user")
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
	userID := c.DefaultQuery("user_id", "demo_user")
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
	userID := c.DefaultQuery("user_id", "demo_user")
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
	userID := c.DefaultQuery("user_id", "demo_user")
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
	userID := c.DefaultQuery("user_id", "demo_user")
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
	userID := c.DefaultQuery("user_id", "demo_user")
	if s.Store == nil {
		c.JSON(http.StatusOK, defaultOnboardingProfile(userID))
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
		Constraints:                  ips.Constraints,
		ApprovalRequiredAboveUSD:     approvalUSD,
		ApprovalRequiredAbovePercent: approvalPct,
		Liabilities:                  liabilities,
	}

	c.JSON(http.StatusOK, profile)
}

func (s *Server) HandleUploadDocument(c *gin.Context) {
	userID := c.DefaultPostForm("user_id", "demo_user")
	documentType := strings.ToLower(strings.TrimSpace(c.PostForm("document_type")))
	targetTable := strings.TrimSpace(c.PostForm("target_table"))

	if documentType == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "document_type is required (transactions, holdings, liabilities, ips)"})
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
	default:
		c.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("unsupported document_type '%s'; accepted types: transactions, holdings, liabilities, ips", documentType)})
		return
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
		ID:          docID,
		Filename:    fileHeader.Filename,
		AccountType: documentType,
		TargetTable: targetTable,
		SizeBytes:   fileHeader.Size,
		UploadedAt:  time.Now().UTC().Format(time.RFC3339),
		Status:      "SUCCESS",
	}

	var recordsParsed int
	ctx := c.Request.Context()

	switch documentType {
	case "transactions":
		reader := csv.NewReader(strings.NewReader(string(fileBytes)))
		records, err := reader.ReadAll()
		if err != nil || len(records) < 2 {
			errMsg := "invalid CSV: must contain header and at least 1 data row"
			if err != nil {
				errMsg = fmt.Sprintf("CSV parse error: %v", err)
			}
			docItem.Status = "FAILED"
			docItem.ErrorMessage = &errMsg
			if s.Store != nil {
				_ = s.Store.SetDocument(ctx, &docItem)
			}
			c.JSON(http.StatusBadRequest, gin.H{"error": errMsg, "document": docItem})
			return
		}
		recordsParsed = len(records) - 1
		if docItem.TargetTable == "" {
			docItem.TargetTable = "checking_transactions"
		}

	case "holdings":
		var snapshot contracts.HoldingsSnapshot
		if err := json.Unmarshal(fileBytes, &snapshot); err != nil {
			errMsg := fmt.Sprintf("JSON parse error for holdings: %v", err)
			docItem.Status = "FAILED"
			docItem.ErrorMessage = &errMsg
			if s.Store != nil {
				_ = s.Store.SetDocument(ctx, &docItem)
			}
			c.JSON(http.StatusBadRequest, gin.H{"error": errMsg, "document": docItem})
			return
		}
		if snapshot.UserID == "" {
			snapshot.UserID = userID
		}
		recordsParsed = len(snapshot.Positions)
		if s.Store != nil {
			if err := s.Store.SetHoldings(ctx, snapshot.UserID, &snapshot); err != nil {
				errMsg := fmt.Sprintf("failed to persist holdings: %v", err)
				docItem.Status = "FAILED"
				docItem.ErrorMessage = &errMsg
				_ = s.Store.SetDocument(ctx, &docItem)
				c.JSON(http.StatusBadRequest, gin.H{"error": errMsg, "document": docItem})
				return
			}
		}

	case "liabilities":
		var snapshot contracts.LiabilitiesSnapshot
		if err := json.Unmarshal(fileBytes, &snapshot); err != nil {
			errMsg := fmt.Sprintf("JSON parse error for liabilities: %v", err)
			docItem.Status = "FAILED"
			docItem.ErrorMessage = &errMsg
			if s.Store != nil {
				_ = s.Store.SetDocument(ctx, &docItem)
			}
			c.JSON(http.StatusBadRequest, gin.H{"error": errMsg, "document": docItem})
			return
		}
		if snapshot.UserID == "" {
			snapshot.UserID = userID
		}
		recordsParsed = len(snapshot.Liabilities)
		if s.Store != nil {
			if err := s.Store.SetLiabilities(ctx, snapshot.UserID, &snapshot); err != nil {
				errMsg := fmt.Sprintf("failed to persist liabilities: %v", err)
				docItem.Status = "FAILED"
				docItem.ErrorMessage = &errMsg
				_ = s.Store.SetDocument(ctx, &docItem)
				c.JSON(http.StatusBadRequest, gin.H{"error": errMsg, "document": docItem})
				return
			}
		}

	case "ips":
		var ips contracts.InvestmentPolicyStatement
		if err := json.Unmarshal(fileBytes, &ips); err != nil {
			errMsg := fmt.Sprintf("JSON parse error for IPS: %v", err)
			docItem.Status = "FAILED"
			docItem.ErrorMessage = &errMsg
			if s.Store != nil {
				_ = s.Store.SetDocument(ctx, &docItem)
			}
			c.JSON(http.StatusBadRequest, gin.H{"error": errMsg, "document": docItem})
			return
		}
		if ips.UserID == "" {
			ips.UserID = userID
		}
		recordsParsed = 1
		if s.Store != nil {
			if err := s.Store.UpdateIPS(ctx, &ips); err != nil {
				errMsg := fmt.Sprintf("failed to update IPS: %v", err)
				docItem.Status = "FAILED"
				docItem.ErrorMessage = &errMsg
				_ = s.Store.SetDocument(ctx, &docItem)
				c.JSON(http.StatusBadRequest, gin.H{"error": errMsg, "document": docItem})
				return
			}
		}
	}

	docItem.RecordsParsed = &recordsParsed
	if s.Store != nil {
		if err := s.Store.SetDocument(ctx, &docItem); err != nil {
			slog.WarnContext(ctx, "Failed to record document metadata in store", "doc_id", docItem.ID, "error", err)
		}
	}

	c.JSON(http.StatusOK, docItem)
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

func defaultOnboardingProfile(userID string) contracts.OnboardingProfile {
	return contracts.OnboardingProfile{
		HasActiveIPS:             true,
		UserID:                   userID,
		IPSID:                    "ips_demo_001",
		Version:                  1,
		TimeHorizonYears:         15,
		KnownUpcomingExpensesUSD: 5000,
		ReserveMonths:            6,
		RiskTolerance:            contracts.RiskToleranceModerate,
		Goals: []contracts.Goal{
			{Name: "Retirement", TargetAmountUSD: 1500000, TargetDate: "2041-01-01"},
			{Name: "Emergency Fund", TargetAmountUSD: 30000, TargetDate: "2026-12-31"},
		},
		TargetBands: []contracts.AllocationBand{
			{AssetClass: "Equity", TargetPercent: 60, MinPercent: 50, MaxPercent: 70},
			{AssetClass: "Fixed Income", TargetPercent: 30, MinPercent: 20, MaxPercent: 40},
			{AssetClass: "Cash", TargetPercent: 10, MinPercent: 5, MaxPercent: 20},
		},
		Constraints: contracts.Constraints{
			ConcentrationLimitPercent: 15,
			ExcludedTickers:           []string{},
			ExcludedSectors:           []string{"Tobacco", "Gambling"},
		},
		ApprovalRequiredAboveUSD:     10000,
		ApprovalRequiredAbovePercent: 5,
		Liabilities: []contracts.Liability{
			{
				LiabilityID:         "liab_mortgage_001",
				Type:                contracts.LiabilityTypeMortgage,
				Description:         ptrString("Primary Residence Mortgage (30yr Fixed @ 3.25%)"),
				BalanceUSD:          420000,
				InterestRatePercent: ptrFloat64(3.25),
				MinimumPaymentUSD:   2450,
			},
		},
	}
}

func ptrString(s string) *string {
	return &s
}
