package contracts_test

import (
	"encoding/json"
	"reflect"
	"testing"
	"time"

	"orchestrator/contracts"
)

// Helper functions to get pointers of literal values.
func ptrString(s string) *string {
	return &s
}

func ptrFloat64(f float64) *float64 {
	return &f
}

func ptrInt(i int) *int {
	return &i
}

func ptrBool(b bool) *bool {
	return &b
}

func ptrTime(t time.Time) *time.Time {
	return &t
}

func TestHoldingsSnapshotRoundTripAndValidation(t *testing.T) {
	now := time.Now().UTC().Truncate(time.Second)

	tests := []struct {
		name          string
		input         contracts.HoldingsSnapshot
		expectedValid bool
	}{
		{
			name: "Fully populated snapshot (valid)",
			input: contracts.HoldingsSnapshot{
				UserID: "user_123",
				AsOf:   now,
				Positions: []contracts.Position{
					{
						Ticker:         "AAPL",
						Quantity:       50.5,
						AssetClass:     "equity",
						MarketValueUSD: 11250.75,
						AccountType:    ptrString("taxable"),
					},
					{
						Ticker:         "BND",
						Quantity:       100,
						AssetClass:     "bonds",
						MarketValueUSD: 7200,
						AccountType:    ptrString("retirement"),
					},
				},
				CashUSD:       ptrFloat64(2500.50),
				TotalValueUSD: ptrFloat64(20951.25),
			},
			expectedValid: true,
		},
		{
			name: "Minimal snapshot (valid)",
			input: contracts.HoldingsSnapshot{
				UserID: "user_456",
				AsOf:   now,
				Positions: []contracts.Position{
					{
						Ticker:         "GOOGL",
						Quantity:       10,
						AssetClass:     "equity",
						MarketValueUSD: 1750,
					},
				},
			},
			expectedValid: true,
		},
		{
			name: "Missing UserID (invalid)",
			input: contracts.HoldingsSnapshot{
				UserID: "",
				AsOf:   now,
			},
			expectedValid: false,
		},
		{
			name: "Missing AsOf time (invalid)",
			input: contracts.HoldingsSnapshot{
				UserID: "user_123",
			},
			expectedValid: false,
		},
		{
			name: "Position with missing ticker (invalid)",
			input: contracts.HoldingsSnapshot{
				UserID: "user_123",
				AsOf:   now,
				Positions: []contracts.Position{
					{
						Ticker:         "",
						Quantity:       10,
						AssetClass:     "equity",
						MarketValueUSD: 100,
					},
				},
			},
			expectedValid: false,
		},
		{
			name: "Position with negative quantity (invalid)",
			input: contracts.HoldingsSnapshot{
				UserID: "user_123",
				AsOf:   now,
				Positions: []contracts.Position{
					{
						Ticker:         "AAPL",
						Quantity:       -5,
						AssetClass:     "equity",
						MarketValueUSD: 100,
					},
				},
			},
			expectedValid: false,
		},
		{
			name: "Position with negative market value (invalid)",
			input: contracts.HoldingsSnapshot{
				UserID: "user_123",
				AsOf:   now,
				Positions: []contracts.Position{
					{
						Ticker:         "AAPL",
						Quantity:       5,
						AssetClass:     "equity",
						MarketValueUSD: -100,
					},
				},
			},
			expectedValid: false,
		},
		{
			name: "Position with empty asset class (invalid)",
			input: contracts.HoldingsSnapshot{
				UserID: "user_123",
				AsOf:   now,
				Positions: []contracts.Position{
					{
						Ticker:         "AAPL",
						Quantity:       5,
						AssetClass:     "",
						MarketValueUSD: 100,
					},
				},
			},
			expectedValid: false,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			// Test Round-Trip if valid
			if tc.expectedValid {
				data, err := json.Marshal(tc.input)
				if err != nil {
					t.Fatalf("failed to marshal: %v", err)
				}

				var actual contracts.HoldingsSnapshot
				if err := json.Unmarshal(data, &actual); err != nil {
					t.Fatalf("failed to unmarshal: %v", err)
				}

				actual.AsOf = actual.AsOf.UTC()

				if !reflect.DeepEqual(tc.input, actual) {
					t.Errorf("round-trip mismatch\nexpected: %+v\ngot: %+v", tc.input, actual)
				}
			}

			// Test Validation
			if tc.input.Validate() != tc.expectedValid {
				t.Errorf("expected Validate() to be %v, got %v", tc.expectedValid, tc.input.Validate())
			}
		})
	}
}

func TestLiabilitiesSnapshotRoundTripAndValidation(t *testing.T) {
	now := time.Now().UTC().Truncate(time.Second)

	tests := []struct {
		name          string
		input         contracts.LiabilitiesSnapshot
		expectedValid bool
	}{
		{
			name: "Fully populated snapshot (valid)",
			input: contracts.LiabilitiesSnapshot{
				UserID: "user_789",
				AsOf:   now,
				Liabilities: []contracts.Liability{
					{
						LiabilityID:         "liab_01",
						Type:                contracts.LiabilityTypeCreditCard,
						Description:         ptrString("Chase Sapphire Preferred"),
						BalanceUSD:          1250.45,
						InterestRatePercent: ptrFloat64(22.99),
						MinimumPaymentUSD:   40,
					},
				},
				TotalLiabilitiesUSD: ptrFloat64(1250.45),
			},
			expectedValid: true,
		},
		{
			name: "Missing UserID (invalid)",
			input: contracts.LiabilitiesSnapshot{
				UserID: "",
				AsOf:   now,
			},
			expectedValid: false,
		},
		{
			name: "Missing liability ID (invalid)",
			input: contracts.LiabilitiesSnapshot{
				UserID: "user_789",
				AsOf:   now,
				Liabilities: []contracts.Liability{
					{
						LiabilityID:       "",
						Type:              contracts.LiabilityTypeOther,
						BalanceUSD:        5000,
						MinimumPaymentUSD: 100,
					},
				},
			},
			expectedValid: false,
		},
		{
			name: "Negative liability balance (invalid)",
			input: contracts.LiabilitiesSnapshot{
				UserID: "user_789",
				AsOf:   now,
				Liabilities: []contracts.Liability{
					{
						LiabilityID:       "liab_01",
						Type:              contracts.LiabilityTypeOther,
						BalanceUSD:        -50,
						MinimumPaymentUSD: 100,
					},
				},
			},
			expectedValid: false,
		},
		{
			name: "Empty liability type (invalid)",
			input: contracts.LiabilitiesSnapshot{
				UserID: "user_789",
				AsOf:   now,
				Liabilities: []contracts.Liability{
					{
						LiabilityID:       "liab_01",
						Type:              "",
						BalanceUSD:        50,
						MinimumPaymentUSD: 10,
					},
				},
			},
			expectedValid: false,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			if tc.expectedValid {
				data, err := json.Marshal(tc.input)
				if err != nil {
					t.Fatalf("failed to marshal: %v", err)
				}

				var actual contracts.LiabilitiesSnapshot
				if err := json.Unmarshal(data, &actual); err != nil {
					t.Fatalf("failed to unmarshal: %v", err)
				}

				actual.AsOf = actual.AsOf.UTC()

				if !reflect.DeepEqual(tc.input, actual) {
					t.Errorf("round-trip mismatch\nexpected: %+v\ngot: %+v", tc.input, actual)
				}
			}

			if tc.input.Validate() != tc.expectedValid {
				t.Errorf("expected Validate() to be %v, got %v", tc.expectedValid, tc.input.Validate())
			}
		})
	}
}

func TestInvestmentPolicyStatementRoundTripAndValidation(t *testing.T) {
	now := time.Now().UTC().Truncate(time.Second)

	tests := []struct {
		name          string
		input         contracts.InvestmentPolicyStatement
		expectedValid bool
		expectActive  bool
	}{
		{
			name: "Comprehensive IPS (valid, active)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_abc123",
				UserID:           "user_123",
				Version:          1,
				Status:           "active",
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    "moderate",
				TimeHorizonYears: 10,
				Goals: []contracts.Goal{
					{
						Name:            "Retirement Pool",
						TargetAmountUSD: 2000000,
						TargetDate:      "2045-12-31",
					},
				},
				LiquidityNeeds: &contracts.LiquidityNeeds{
					ReserveMonths:            ptrFloat64(6),
					KnownUpcomingExpensesUSD: ptrFloat64(15000),
				},
				TargetAllocation: []contracts.AllocationBand{
					{
						AssetClass:    "equity",
						TargetPercent: 60,
						MinPercent:    50,
						MaxPercent:    70,
					},
				},
				Constraints: contracts.Constraints{
					ConcentrationLimitPercent: 15,
				},
				CreatedAt: now,
			},
			expectedValid: true,
			expectActive:  true,
		},
		{
			name: "Draft IPS (valid, inactive)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_def456",
				UserID:           "user_456",
				Version:          1,
				Status:           "draft",
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    "conservative",
				TimeHorizonYears: 5,
				TargetAllocation: []contracts.AllocationBand{
					{
						AssetClass:    "equity",
						TargetPercent: 30,
						MinPercent:    20,
						MaxPercent:    40,
					},
				},
				Constraints: contracts.Constraints{
					ConcentrationLimitPercent: 20,
				},
				CreatedAt: now,
			},
			expectedValid: true,
			expectActive:  false,
		},
		{
			name: "Missing IPSID (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "",
				UserID:           "user_123",
				Status:           "draft",
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    "moderate",
				TimeHorizonYears: 10,
			},
			expectedValid: false,
		},
		{
			name: "Version < 1 (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_123",
				UserID:           "user_123",
				Version:          0,
				Status:           "draft",
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    "moderate",
				TimeHorizonYears: 10,
			},
			expectedValid: false,
		},
		{
			name: "Negative TimeHorizon (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_123",
				UserID:           "user_123",
				Version:          1,
				Status:           "draft",
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    "moderate",
				TimeHorizonYears: -1,
			},
			expectedValid: false,
		},
		{
			name: "AllocationBand empty AssetClass (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_123",
				UserID:           "user_123",
				Version:          1,
				Status:           "draft",
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    "moderate",
				TimeHorizonYears: 10,
				TargetAllocation: []contracts.AllocationBand{
					{
						AssetClass:    "",
						TargetPercent: 60,
						MinPercent:    50,
						MaxPercent:    70,
					},
				},
			},
			expectedValid: false,
		},
		{
			name: "AllocationBand target negative (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_123",
				UserID:           "user_123",
				Version:          1,
				Status:           "draft",
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    "moderate",
				TimeHorizonYears: 10,
				TargetAllocation: []contracts.AllocationBand{
					{
						AssetClass:    "equity",
						TargetPercent: -1,
						MinPercent:    50,
						MaxPercent:    70,
					},
				},
			},
			expectedValid: false,
		},
		{
			name: "AllocationBand target too high (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_123",
				UserID:           "user_123",
				Version:          1,
				Status:           "draft",
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    "moderate",
				TimeHorizonYears: 10,
				TargetAllocation: []contracts.AllocationBand{
					{
						AssetClass:    "equity",
						TargetPercent: 101,
						MinPercent:    50,
						MaxPercent:    70,
					},
				},
			},
			expectedValid: false,
		},
		{
			name: "AllocationBand min negative (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_123",
				UserID:           "user_123",
				Version:          1,
				Status:           "draft",
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    "moderate",
				TimeHorizonYears: 10,
				TargetAllocation: []contracts.AllocationBand{
					{
						AssetClass:    "equity",
						TargetPercent: 60,
						MinPercent:    -5,
						MaxPercent:    70,
					},
				},
			},
			expectedValid: false,
		},
		{
			name: "AllocationBand min too high (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_123",
				UserID:           "user_123",
				Version:          1,
				Status:           "draft",
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    "moderate",
				TimeHorizonYears: 10,
				TargetAllocation: []contracts.AllocationBand{
					{
						AssetClass:    "equity",
						TargetPercent: 60,
						MinPercent:    105,
						MaxPercent:    70,
					},
				},
			},
			expectedValid: false,
		},
		{
			name: "AllocationBand max negative (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_123",
				UserID:           "user_123",
				Version:          1,
				Status:           "draft",
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    "moderate",
				TimeHorizonYears: 10,
				TargetAllocation: []contracts.AllocationBand{
					{
						AssetClass:    "equity",
						TargetPercent: 60,
						MinPercent:    50,
						MaxPercent:    -10,
					},
				},
			},
			expectedValid: false,
		},
		{
			name: "AllocationBand max too high (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_123",
				UserID:           "user_123",
				Version:          1,
				Status:           "draft",
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    "moderate",
				TimeHorizonYears: 10,
				TargetAllocation: []contracts.AllocationBand{
					{
						AssetClass:    "equity",
						TargetPercent: 60,
						MinPercent:    50,
						MaxPercent:    102,
					},
				},
			},
			expectedValid: false,
		},
		{
			name: "Negative concentration limit (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_abc123",
				UserID:           "user_123",
				Version:          1,
				Status:           "draft",
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    "moderate",
				TimeHorizonYears: 10,
				TargetAllocation: []contracts.AllocationBand{
					{
						AssetClass:    "equity",
						TargetPercent: 100,
					},
				},
				Constraints: contracts.Constraints{
					ConcentrationLimitPercent: -5,
				},
				CreatedAt: now,
			},
			expectedValid: false,
		},
		{
			name: "Concentration limit too high (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_abc123",
				UserID:           "user_123",
				Version:          1,
				Status:           "draft",
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    "moderate",
				TimeHorizonYears: 10,
				TargetAllocation: []contracts.AllocationBand{
					{
						AssetClass:    "equity",
						TargetPercent: 100,
					},
				},
				Constraints: contracts.Constraints{
					ConcentrationLimitPercent: 105,
				},
				CreatedAt: now,
			},
			expectedValid: false,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			if tc.expectedValid {
				data, err := json.Marshal(tc.input)
				if err != nil {
					t.Fatalf("failed to marshal: %v", err)
				}

				var actual contracts.InvestmentPolicyStatement
				if err := json.Unmarshal(data, &actual); err != nil {
					t.Fatalf("failed to unmarshal: %v", err)
				}

				actual.CreatedAt = actual.CreatedAt.UTC()

				if !reflect.DeepEqual(tc.input, actual) {
					t.Errorf("round-trip mismatch\nexpected: %+v\ngot: %+v", tc.input, actual)
				}
			}

			if tc.input.Validate() != tc.expectedValid {
				t.Errorf("expected Validate() to be %v, got %v", tc.expectedValid, tc.input.Validate())
			}

			if tc.input.IsActive() != tc.expectActive {
				t.Errorf("expected IsActive() to be %v, got %v", tc.expectActive, tc.input.IsActive())
			}
		})
	}
}

func TestProposedActionRoundTripAndValidation(t *testing.T) {
	now := time.Now().UTC().Truncate(time.Second)

	tests := []struct {
		name          string
		input         contracts.ProposedAction
		expectedValid bool
		expectTrade   bool
	}{
		{
			name: "Fully loaded ProposedAction (valid, trade)",
			input: contracts.ProposedAction{
				ActionID:               "action_777",
				SessionID:              "session_xyz",
				Type:                   "trade",
				Ticker:                 "AAPL",
				Side:                   "buy",
				Quantity:               15,
				OrderType:              "limit",
				LimitPriceUSD:          ptrFloat64(150.25),
				EstimatedPriceUSD:      ptrFloat64(150),
				EstimatedValueUSD:      ptrFloat64(2250),
				Rationale:              "Rebalancing portfolio.",
				SupportingResearchRefs: []string{"res_01"},
				IPSVersionReferenced: contracts.IPSVersionRef{
					IPSID:   "ips_111",
					Version: 2,
				},
				ProposedBySkillVersion: contracts.SkillVersionRef{
					SkillName:    "action-drafting",
					SkillVersion: "0.1.0",
				},
				Status:    "drafted",
				CreatedAt: now,
			},
			expectedValid: true,
			expectTrade:   true,
		},
		{
			name: "Action type non-trade (valid, not trade)",
			input: contracts.ProposedAction{
				ActionID:  "action_888",
				SessionID: "session_abc",
				Type:      "other",
				Ticker:    "MSFT",
				Side:      "sell",
				Quantity:  10,
				OrderType: "market",
				Rationale: "Raising cash.",
				IPSVersionReferenced: contracts.IPSVersionRef{
					IPSID:   "ips_222",
					Version: 1,
				},
				ProposedBySkillVersion: contracts.SkillVersionRef{
					SkillName:    "action-drafting",
					SkillVersion: "0.1.0",
				},
				Status:    "pending_approval",
				CreatedAt: now,
			},
			expectedValid: true,
			expectTrade:   false,
		},
		{
			name: "Missing ActionID (invalid)",
			input: contracts.ProposedAction{
				ActionID:  "",
				SessionID: "session_abc",
				Type:      "trade",
			},
			expectedValid: false,
			expectTrade:   true,
		},
		{
			name: "Zero quantity (invalid)",
			input: contracts.ProposedAction{
				ActionID:  "action_888",
				SessionID: "session_abc",
				Type:      "trade",
				Ticker:    "MSFT",
				Side:      "sell",
				Quantity:  0,
			},
			expectedValid: false,
			expectTrade:   true,
		},
		{
			name: "Missing referenced IPS ID (invalid)",
			input: contracts.ProposedAction{
				ActionID:  "action_888",
				SessionID: "session_abc",
				Type:      "trade",
				Ticker:    "MSFT",
				Side:      "sell",
				Quantity:  10,
				Rationale: "Raising cash.",
				IPSVersionReferenced: contracts.IPSVersionRef{
					IPSID:   "",
					Version: 1,
				},
				ProposedBySkillVersion: contracts.SkillVersionRef{
					SkillName:    "action-drafting",
					SkillVersion: "0.1.0",
				},
				Status:    "pending_approval",
				CreatedAt: now,
			},
			expectedValid: false,
			expectTrade:   true,
		},
		{
			name: "Missing proposing skill name (invalid)",
			input: contracts.ProposedAction{
				ActionID:  "action_888",
				SessionID: "session_abc",
				Type:      "trade",
				Ticker:    "MSFT",
				Side:      "sell",
				Quantity:  10,
				Rationale: "Raising cash.",
				IPSVersionReferenced: contracts.IPSVersionRef{
					IPSID:   "ips_1",
					Version: 1,
				},
				ProposedBySkillVersion: contracts.SkillVersionRef{
					SkillName:    "",
					SkillVersion: "0.1.0",
				},
				Status:    "pending_approval",
				CreatedAt: now,
			},
			expectedValid: false,
			expectTrade:   true,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			if tc.expectedValid {
				data, err := json.Marshal(tc.input)
				if err != nil {
					t.Fatalf("failed to marshal: %v", err)
				}

				var actual contracts.ProposedAction
				if err := json.Unmarshal(data, &actual); err != nil {
					t.Fatalf("failed to unmarshal: %v", err)
				}

				actual.CreatedAt = actual.CreatedAt.UTC()

				if !reflect.DeepEqual(tc.input, actual) {
					t.Errorf("round-trip mismatch\nexpected: %+v\ngot: %+v", tc.input, actual)
				}
			}

			if tc.input.Validate() != tc.expectedValid {
				t.Errorf("expected Validate() to be %v, got %v", tc.expectedValid, tc.input.Validate())
			}

			if tc.input.IsTrade() != tc.expectTrade {
				t.Errorf("expected IsTrade() to be %v, got %v", tc.expectTrade, tc.input.IsTrade())
			}
		})
	}
}

func TestReviewerVerdictRoundTripAndValidation(t *testing.T) {
	now := time.Now().UTC().Truncate(time.Second)

	tests := []struct {
		name          string
		input         contracts.ReviewerVerdict
		expectedValid bool
	}{
		{
			name: "Valid ReviewerVerdict",
			input: contracts.ReviewerVerdict{
				VerdictID: "verdict_333",
				ActionID:  "action_777",
				IPSVersionCheckedAgainst: contracts.IPSVersionRef{
					IPSID:   "ips_111",
					Version: 2,
				},
				RuleResults: []contracts.RuleResult{
					{
						RuleID:      "excluded-ticker",
						Description: "Check ticker is not in excluded_tickers list.",
						Passed:      true,
					},
				},
				OverallPass:           true,
				RequiresHumanApproval: true,
				ReviewerSkillVersion: contracts.SkillVersionRef{
					SkillName:    "reviewer-critic",
					SkillVersion: "1.0.0",
				},
				ReviewedAt: now,
			},
			expectedValid: true,
		},
		{
			name: "Missing Verdict ID (invalid)",
			input: contracts.ReviewerVerdict{
				VerdictID:  "",
				ActionID:   "action_777",
				ReviewedAt: now,
			},
			expectedValid: false,
		},
		{
			name: "Zero rule results (invalid)",
			input: contracts.ReviewerVerdict{
				VerdictID:   "verdict_333",
				ActionID:    "action_777",
				ReviewedAt:  now,
				RuleResults: []contracts.RuleResult{},
			},
			expectedValid: false,
		},
		{
			name: "Rule with missing rule ID (invalid)",
			input: contracts.ReviewerVerdict{
				VerdictID:  "verdict_333",
				ActionID:   "action_777",
				ReviewedAt: now,
				RuleResults: []contracts.RuleResult{
					{
						RuleID:      "",
						Description: "Descr",
						Passed:      true,
					},
				},
			},
			expectedValid: false,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			if tc.expectedValid {
				data, err := json.Marshal(tc.input)
				if err != nil {
					t.Fatalf("failed to marshal: %v", err)
				}

				var actual contracts.ReviewerVerdict
				if err := json.Unmarshal(data, &actual); err != nil {
					t.Fatalf("failed to unmarshal: %v", err)
				}

				actual.ReviewedAt = actual.ReviewedAt.UTC()

				if !reflect.DeepEqual(tc.input, actual) {
					t.Errorf("round-trip mismatch\nexpected: %+v\ngot: %+v", tc.input, actual)
				}
			}

			if tc.input.Validate() != tc.expectedValid {
				t.Errorf("expected Validate() to be %v, got %v", tc.expectedValid, tc.input.Validate())
			}
		})
	}
}

func TestAuditLogEntryRoundTripAndValidation(t *testing.T) {
	now := time.Now().UTC().Truncate(time.Second)

	tests := []struct {
		name          string
		input         contracts.AuditLogEntry
		expectedValid bool
	}{
		{
			name: "Valid AuditLogEntry",
			input: contracts.AuditLogEntry{
				LogID:     "log_001",
				EventType: "action_proposed",
				Timestamp: now,
				Actor: contracts.ActorRef{
					Type: "agent",
				},
			},
			expectedValid: true,
		},
		{
			name: "Missing log ID (invalid)",
			input: contracts.AuditLogEntry{
				LogID:     "",
				EventType: "action_proposed",
				Timestamp: now,
				Actor: contracts.ActorRef{
					Type: "agent",
				},
			},
			expectedValid: false,
		},
		{
			name: "Missing actor type (invalid)",
			input: contracts.AuditLogEntry{
				LogID:     "log_001",
				EventType: "action_proposed",
				Timestamp: now,
				Actor: contracts.ActorRef{
					Type: "",
				},
			},
			expectedValid: false,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			if tc.expectedValid {
				data, err := json.Marshal(tc.input)
				if err != nil {
					t.Fatalf("failed to marshal: %v", err)
				}

				var actual contracts.AuditLogEntry
				if err := json.Unmarshal(data, &actual); err != nil {
					t.Fatalf("failed to unmarshal: %v", err)
				}

				actual.Timestamp = actual.Timestamp.UTC()

				if !reflect.DeepEqual(tc.input, actual) {
					t.Errorf("round-trip mismatch\nexpected: %+v\ngot: %+v", tc.input, actual)
				}
			}

			if tc.input.Validate() != tc.expectedValid {
				t.Errorf("expected Validate() to be %v, got %v", tc.expectedValid, tc.input.Validate())
			}
		})
	}
}
