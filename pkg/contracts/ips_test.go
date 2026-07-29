package contracts_test

import (
	"encoding/json"
	"reflect"
	"testing"
	"time"

	"portfolio-copilot/pkg/contracts"
)

func TestInvestmentPolicyStatementRoundTripAndValidation(t *testing.T) {
	now := time.Now().UTC().Truncate(time.Second)

	accountTypeTaxable := contracts.AccountTypeTaxable
	accountTypeInvalid := contracts.AccountType("invalid_acc")
	triggerThreshold := contracts.RebalancingTriggerThreshold
	triggerInvalid := contracts.RebalancingTriggerType("invalid_trig")

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
				Status:           contracts.IPSStatusActive,
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    contracts.RiskToleranceModerate,
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
					AccountType:               &accountTypeTaxable,
				},
				RebalancingRules: &contracts.RebalancingRules{
					TriggerType:              &triggerThreshold,
					DriftThresholdPercent:    ptrFloat64(5.0),
					RebalancingFrequencyDays: ptrInt(30),
				},
				ApprovalRequiredAboveUSD:     ptrFloat64(5000),
				ApprovalRequiredAbovePercent: ptrFloat64(10.0),
				CreatedAt:                    now,
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
				Status:           contracts.IPSStatusDraft,
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    contracts.RiskToleranceConservative,
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
				Status:           contracts.IPSStatusDraft,
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    contracts.RiskToleranceModerate,
				TimeHorizonYears: 10,
				CreatedAt:        now,
			},
			expectedValid: false,
		},
		{
			name: "Missing CreatedAt (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_123",
				UserID:           "user_123",
				Version:          1,
				Status:           contracts.IPSStatusActive,
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    contracts.RiskToleranceModerate,
				TimeHorizonYears: 10,
			},
			expectedValid: false,
		},
		{
			name: "Invalid status enum (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_123",
				UserID:           "user_123",
				Version:          1,
				Status:           contracts.IPSStatus("archived"),
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    contracts.RiskToleranceModerate,
				TimeHorizonYears: 10,
				CreatedAt:        now,
			},
			expectedValid: false,
		},
		{
			name: "Invalid risk tolerance enum (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_123",
				UserID:           "user_123",
				Version:          1,
				Status:           contracts.IPSStatusActive,
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    contracts.RiskTolerance("extreme"),
				TimeHorizonYears: 10,
				CreatedAt:        now,
			},
			expectedValid: false,
		},
		{
			name: "Goal with empty name (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_123",
				UserID:           "user_123",
				Version:          1,
				Status:           contracts.IPSStatusActive,
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    contracts.RiskToleranceModerate,
				TimeHorizonYears: 10,
				Goals: []contracts.Goal{
					{Name: "", TargetAmountUSD: 100, TargetDate: "2030-01-01"},
				},
				TargetAllocation: []contracts.AllocationBand{
					{AssetClass: "equity", TargetPercent: 100, MinPercent: 0, MaxPercent: 100},
				},
				CreatedAt: now,
			},
			expectedValid: false,
		},
		{
			name: "Goal with negative target amount (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_123",
				UserID:           "user_123",
				Version:          1,
				Status:           contracts.IPSStatusActive,
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    contracts.RiskToleranceModerate,
				TimeHorizonYears: 10,
				Goals: []contracts.Goal{
					{Name: "House", TargetAmountUSD: -500, TargetDate: "2030-01-01"},
				},
				TargetAllocation: []contracts.AllocationBand{
					{AssetClass: "equity", TargetPercent: 100, MinPercent: 0, MaxPercent: 100},
				},
				CreatedAt: now,
			},
			expectedValid: false,
		},
		{
			name: "Goal with empty target date (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_123",
				UserID:           "user_123",
				Version:          1,
				Status:           contracts.IPSStatusActive,
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    contracts.RiskToleranceModerate,
				TimeHorizonYears: 10,
				Goals: []contracts.Goal{
					{Name: "House", TargetAmountUSD: 500, TargetDate: ""},
				},
				TargetAllocation: []contracts.AllocationBand{
					{AssetClass: "equity", TargetPercent: 100, MinPercent: 0, MaxPercent: 100},
				},
				CreatedAt: now,
			},
			expectedValid: false,
		},
		{
			name: "LiquidityNeeds with negative reserve_months (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_123",
				UserID:           "user_123",
				Version:          1,
				Status:           contracts.IPSStatusActive,
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    contracts.RiskToleranceModerate,
				TimeHorizonYears: 10,
				LiquidityNeeds: &contracts.LiquidityNeeds{
					ReserveMonths: ptrFloat64(-3),
				},
				TargetAllocation: []contracts.AllocationBand{
					{AssetClass: "equity", TargetPercent: 100, MinPercent: 0, MaxPercent: 100},
				},
				CreatedAt: now,
			},
			expectedValid: false,
		},
		{
			name: "LiquidityNeeds with negative upcoming expenses (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_123",
				UserID:           "user_123",
				Version:          1,
				Status:           contracts.IPSStatusActive,
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    contracts.RiskToleranceModerate,
				TimeHorizonYears: 10,
				LiquidityNeeds: &contracts.LiquidityNeeds{
					KnownUpcomingExpensesUSD: ptrFloat64(-500),
				},
				TargetAllocation: []contracts.AllocationBand{
					{AssetClass: "equity", TargetPercent: 100, MinPercent: 0, MaxPercent: 100},
				},
				CreatedAt: now,
			},
			expectedValid: false,
		},
		{
			name: "Empty target_allocation list (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_123",
				UserID:           "user_123",
				Version:          1,
				Status:           contracts.IPSStatusActive,
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    contracts.RiskToleranceModerate,
				TimeHorizonYears: 10,
				TargetAllocation: []contracts.AllocationBand{},
				CreatedAt:        now,
			},
			expectedValid: false,
		},
		{
			name: "Invalid account type in constraints (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_123",
				UserID:           "user_123",
				Version:          1,
				Status:           contracts.IPSStatusDraft,
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    contracts.RiskToleranceModerate,
				TimeHorizonYears: 10,
				TargetAllocation: []contracts.AllocationBand{
					{AssetClass: "equity", TargetPercent: 50, MinPercent: 40, MaxPercent: 60},
				},
				Constraints: contracts.Constraints{
					ConcentrationLimitPercent: 15,
					AccountType:               &accountTypeInvalid,
				},
				CreatedAt: now,
			},
			expectedValid: false,
		},
		{
			name: "Invalid rebalancing trigger type (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_123",
				UserID:           "user_123",
				Version:          1,
				Status:           contracts.IPSStatusDraft,
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    contracts.RiskToleranceModerate,
				TimeHorizonYears: 10,
				TargetAllocation: []contracts.AllocationBand{
					{AssetClass: "equity", TargetPercent: 50, MinPercent: 40, MaxPercent: 60},
				},
				RebalancingRules: &contracts.RebalancingRules{
					TriggerType: &triggerInvalid,
				},
				CreatedAt: now,
			},
			expectedValid: false,
		},
		{
			name: "RebalancingRules with negative drift threshold (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_123",
				UserID:           "user_123",
				Version:          1,
				Status:           contracts.IPSStatusDraft,
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    contracts.RiskToleranceModerate,
				TimeHorizonYears: 10,
				TargetAllocation: []contracts.AllocationBand{
					{AssetClass: "equity", TargetPercent: 50, MinPercent: 40, MaxPercent: 60},
				},
				RebalancingRules: &contracts.RebalancingRules{
					DriftThresholdPercent: ptrFloat64(-2.0),
				},
				CreatedAt: now,
			},
			expectedValid: false,
		},
		{
			name: "RebalancingRules with frequency < 1 (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_123",
				UserID:           "user_123",
				Version:          1,
				Status:           contracts.IPSStatusDraft,
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    contracts.RiskToleranceModerate,
				TimeHorizonYears: 10,
				TargetAllocation: []contracts.AllocationBand{
					{AssetClass: "equity", TargetPercent: 50, MinPercent: 40, MaxPercent: 60},
				},
				RebalancingRules: &contracts.RebalancingRules{
					RebalancingFrequencyDays: ptrInt(0),
				},
				CreatedAt: now,
			},
			expectedValid: false,
		},
		{
			name: "ApprovalRequiredAboveUSD negative (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:                    "ips_123",
				UserID:                   "user_123",
				Version:                  1,
				Status:                   contracts.IPSStatusDraft,
				EffectiveDate:            "2026-07-28",
				RiskTolerance:            contracts.RiskToleranceModerate,
				TimeHorizonYears:         10,
				TargetAllocation:         []contracts.AllocationBand{{AssetClass: "equity", TargetPercent: 100, MinPercent: 0, MaxPercent: 100}},
				ApprovalRequiredAboveUSD: ptrFloat64(-100),
				CreatedAt:                now,
			},
			expectedValid: false,
		},
		{
			name: "ApprovalRequiredAbovePercent negative (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:                        "ips_123",
				UserID:                       "user_123",
				Version:                      1,
				Status:                       contracts.IPSStatusDraft,
				EffectiveDate:                "2026-07-28",
				RiskTolerance:                contracts.RiskToleranceModerate,
				TimeHorizonYears:             10,
				TargetAllocation:             []contracts.AllocationBand{{AssetClass: "equity", TargetPercent: 100, MinPercent: 0, MaxPercent: 100}},
				ApprovalRequiredAbovePercent: ptrFloat64(-5),
				CreatedAt:                    now,
			},
			expectedValid: false,
		},
		{
			name: "ApprovalRequiredAbovePercent > 100 (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:                        "ips_123",
				UserID:                       "user_123",
				Version:                      1,
				Status:                       contracts.IPSStatusDraft,
				EffectiveDate:                "2026-07-28",
				RiskTolerance:                contracts.RiskToleranceModerate,
				TimeHorizonYears:             10,
				TargetAllocation:             []contracts.AllocationBand{{AssetClass: "equity", TargetPercent: 100, MinPercent: 0, MaxPercent: 100}},
				ApprovalRequiredAbovePercent: ptrFloat64(105),
				CreatedAt:                    now,
			},
			expectedValid: false,
		},
		{
			name: "AllocationBand with min_percent > target_percent (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_123",
				UserID:           "user_123",
				Version:          1,
				Status:           contracts.IPSStatusDraft,
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    contracts.RiskToleranceModerate,
				TimeHorizonYears: 10,
				TargetAllocation: []contracts.AllocationBand{
					{AssetClass: "equity", TargetPercent: 60, MinPercent: 70, MaxPercent: 80},
				},
				CreatedAt: now,
			},
			expectedValid: false,
		},
		{
			name: "AllocationBand with target_percent > max_percent (invalid)",
			input: contracts.InvestmentPolicyStatement{
				IPSID:            "ips_123",
				UserID:           "user_123",
				Version:          1,
				Status:           contracts.IPSStatusDraft,
				EffectiveDate:    "2026-07-28",
				RiskTolerance:    contracts.RiskToleranceModerate,
				TimeHorizonYears: 10,
				TargetAllocation: []contracts.AllocationBand{
					{AssetClass: "equity", TargetPercent: 60, MinPercent: 40, MaxPercent: 50},
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

			if tc.expectedValid && tc.input.IsActive() != tc.expectActive {
				t.Errorf("expected IsActive() to be %v, got %v", tc.expectActive, tc.input.IsActive())
			}
		})
	}
}
