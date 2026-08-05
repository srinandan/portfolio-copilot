package main

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"time"

	"github.com/gin-gonic/gin"
	"portfolio-copilot/pkg/contracts"
	"portfolio-copilot/pkg/store"
)

// GatewayServer holds dependencies for HTTP handlers, including the Firestore store client.
type GatewayServer struct {
	Store *store.Client
}

// NewGatewayServer initializes a GatewayServer, attempting to connect to Firestore if configured.
func NewGatewayServer() *GatewayServer {
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
		slog.Info("No PROJECT_ID set; gateway running in fallback mode")
	}
	return &GatewayServer{
		Store: storeClient,
	}
}

func (s *GatewayServer) HandleGetHoldings(c *gin.Context) {
	userID := c.DefaultQuery("user_id", "usr_default")
	if s.Store != nil {
		snapshot, err := s.Store.GetHoldings(c.Request.Context(), userID)
		if err == nil && snapshot != nil {
			c.JSON(http.StatusOK, snapshot)
			return
		}
		if !store.IsNotFound(err) {
			slog.ErrorContext(c.Request.Context(), "Error reading holdings from Firestore", "error", err)
		}
	}
	c.JSON(http.StatusOK, defaultHoldings())
}

func (s *GatewayServer) HandleGetSpendingReport(c *gin.Context) {
	userID := c.DefaultQuery("user_id", "usr_default")
	if s.Store != nil {
		report, err := s.Store.GetSpendingReport(c.Request.Context(), userID)
		if err == nil && report != nil {
			c.JSON(http.StatusOK, report)
			return
		}
		if !store.IsNotFound(err) {
			slog.ErrorContext(c.Request.Context(), "Error reading spending report from Firestore", "error", err)
		}
	}
	c.JSON(http.StatusOK, defaultSpendingReport())
}

func (s *GatewayServer) HandleGetDriftReport(c *gin.Context) {
	userID := c.DefaultQuery("user_id", "usr_default")
	if s.Store != nil {
		report, err := s.Store.GetDriftReport(c.Request.Context(), userID)
		if err == nil && report != nil {
			c.JSON(http.StatusOK, report)
			return
		}
		if !store.IsNotFound(err) {
			slog.ErrorContext(c.Request.Context(), "Error reading drift report from Firestore", "error", err)
		}
	}
	c.JSON(http.StatusOK, defaultDriftReport())
}

func (s *GatewayServer) HandleGetDocuments(c *gin.Context) {
	userID := c.DefaultQuery("user_id", "usr_default")
	if s.Store != nil {
		items, err := s.Store.GetDocuments(c.Request.Context(), userID)
		if err == nil && len(items) > 0 {
			c.JSON(http.StatusOK, items)
			return
		}
		if !store.IsNotFound(err) {
			slog.ErrorContext(c.Request.Context(), "Error reading documents from Firestore", "error", err)
		}
	}
	c.JSON(http.StatusOK, defaultDocuments())
}

func (s *GatewayServer) HandleApproveAction(c *gin.Context) {
	actionID := c.Param("action_id")
	if actionID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "action_id required"})
		return
	}
	if s.Store != nil {
		err := s.Store.UpdateProposedActionStatus(c.Request.Context(), actionID, contracts.ActionStatusApproved)
		if err != nil && !store.IsNotFound(err) {
			slog.ErrorContext(c.Request.Context(), "Error updating action status to APPROVED", "error", err)
		}
		action, err := s.Store.GetProposedAction(c.Request.Context(), actionID)
		if err == nil && action != nil {
			c.JSON(http.StatusOK, action)
			return
		}
	}
	c.JSON(http.StatusOK, defaultProposedAction(actionID, contracts.ActionStatusApproved))
}

func (s *GatewayServer) HandleRejectAction(c *gin.Context) {
	actionID := c.Param("action_id")
	if actionID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "action_id required"})
		return
	}
	if s.Store != nil {
		err := s.Store.UpdateProposedActionStatus(c.Request.Context(), actionID, contracts.ActionStatusRejected)
		if err != nil && !store.IsNotFound(err) {
			slog.ErrorContext(c.Request.Context(), "Error updating action status to REJECTED", "error", err)
		}
		action, err := s.Store.GetProposedAction(c.Request.Context(), actionID)
		if err == nil && action != nil {
			c.JSON(http.StatusOK, action)
			return
		}
	}
	c.JSON(http.StatusOK, defaultProposedAction(actionID, contracts.ActionStatusRejected))
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
		TotalValueUSD: ptrFloat64(1248500.0),
		CashUSD:       ptrFloat64(62400.0),
		AsOf:          now,
		Positions: []contracts.Position{
			{
				Ticker:          "AAPL",
				Name:            "Apple Inc.",
				AssetClass:      "Equities (US)",
				Quantity:        120,
				CurrentPriceUSD: 170.41,
				CurrentValueUSD: 20449.2,
				MarketValueUSD:  20449.2,
			},
			{
				Ticker:          "VOO",
				Name:            "Vanguard S&P 500 ETF",
				AssetClass:      "Equities (US)",
				Quantity:        45,
				CurrentPriceUSD: 404.45,
				CurrentValueUSD: 18200.25,
				MarketValueUSD:  18200.25,
			},
			{
				Ticker:          "MSFT",
				Name:            "Microsoft Corp.",
				AssetClass:      "Equities (US)",
				Quantity:        50,
				CurrentPriceUSD: 410.0,
				CurrentValueUSD: 20500.0,
				MarketValueUSD:  20500.0,
			},
		},
	}
}

func defaultSpendingReport() *contracts.SpendingReport {
	return &contracts.SpendingReport{
		UserID:          "usr_default",
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
		AsOf:                 time.Now().UTC().Format("2006-01-02"),
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
			Filename:      "Fidelity_Stmt_Oct2023.pdf",
			SizeBytes:     1258291,
			UploadedAt:    "2023-10-24T09:41:00Z",
			Status:        "SUCCESS",
			RecordsParsed: ptrInt(42),
		},
	}
}

func defaultProposedAction(actionID string, status contracts.ActionStatus) *contracts.ProposedAction {
	now := time.Now().UTC()
	return &contracts.ProposedAction{
		ActionID:  actionID,
		SessionID: "sess-default",
		Type:      contracts.ActionTypeTrade,
		Status:    status,
		Rationale: fmt.Sprintf("Action %s changed status to %s by human in UI.", actionID, status),
		CreatedAt: now,
	}
}
