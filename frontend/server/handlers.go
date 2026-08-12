package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
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
