package contracts_test

import (
	"encoding/json"
	"reflect"
	"testing"
	"time"

	"portfolio-copilot/pkg/contracts"
)

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
				Type:                   contracts.ActionTypeTrade,
				Ticker:                 "AAPL",
				Side:                   contracts.ActionSideBuy,
				Quantity:               15,
				OrderType:              contracts.OrderTypeLimit,
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
				Status:    contracts.ActionStatusDrafted,
				CreatedAt: now,
			},
			expectedValid: true,
			expectTrade:   true,
		},
		{
			name: "Market order ProposedAction (valid, no limit price)",
			input: contracts.ProposedAction{
				ActionID:  "action_888",
				SessionID: "session_abc",
				Type:      contracts.ActionTypeTrade,
				Ticker:    "MSFT",
				Side:      contracts.ActionSideSell,
				Quantity:  10,
				OrderType: contracts.OrderTypeMarket,
				Rationale: "Raising cash.",
				IPSVersionReferenced: contracts.IPSVersionRef{
					IPSID:   "ips_222",
					Version: 1,
				},
				ProposedBySkillVersion: contracts.SkillVersionRef{
					SkillName:    "action-drafting",
					SkillVersion: "0.1.0",
				},
				Status:    contracts.ActionStatusPendingApproval,
				CreatedAt: now,
			},
			expectedValid: true,
			expectTrade:   true,
		},
		{
			name: "Non-trade action type (invalid according to schema enum)",
			input: contracts.ProposedAction{
				ActionID:  "action_999",
				SessionID: "session_abc",
				Type:      contracts.ActionType("transfer"),
				Ticker:    "MSFT",
				Side:      contracts.ActionSideSell,
				Quantity:  10,
				OrderType: contracts.OrderTypeMarket,
				Rationale: "Transferring assets.",
				IPSVersionReferenced: contracts.IPSVersionRef{
					IPSID:   "ips_222",
					Version: 1,
				},
				ProposedBySkillVersion: contracts.SkillVersionRef{
					SkillName:    "action-drafting",
					SkillVersion: "0.1.0",
				},
				Status:    contracts.ActionStatusPendingApproval,
				CreatedAt: now,
			},
			expectedValid: false,
			expectTrade:   false,
		},
		{
			name: "Limit order missing limit_price_usd (invalid)",
			input: contracts.ProposedAction{
				ActionID:  "action_777",
				SessionID: "session_xyz",
				Type:      contracts.ActionTypeTrade,
				Ticker:    "AAPL",
				Side:      contracts.ActionSideBuy,
				Quantity:  15,
				OrderType: contracts.OrderTypeLimit,
				Rationale: "Rebalancing portfolio.",
				IPSVersionReferenced: contracts.IPSVersionRef{
					IPSID:   "ips_111",
					Version: 2,
				},
				ProposedBySkillVersion: contracts.SkillVersionRef{
					SkillName:    "action-drafting",
					SkillVersion: "0.1.0",
				},
				Status:    contracts.ActionStatusDrafted,
				CreatedAt: now,
			},
			expectedValid: false,
			expectTrade:   true,
		},
		{
			name: "Limit order with zero limit_price_usd (invalid)",
			input: contracts.ProposedAction{
				ActionID:      "action_777",
				SessionID:     "session_xyz",
				Type:          contracts.ActionTypeTrade,
				Ticker:        "AAPL",
				Side:          contracts.ActionSideBuy,
				Quantity:      15,
				OrderType:     contracts.OrderTypeLimit,
				LimitPriceUSD: ptrFloat64(0),
				Rationale:     "Rebalancing portfolio.",
				IPSVersionReferenced: contracts.IPSVersionRef{
					IPSID:   "ips_111",
					Version: 2,
				},
				ProposedBySkillVersion: contracts.SkillVersionRef{
					SkillName:    "action-drafting",
					SkillVersion: "0.1.0",
				},
				Status:    contracts.ActionStatusDrafted,
				CreatedAt: now,
			},
			expectedValid: false,
			expectTrade:   true,
		},
		{
			name: "Market order with limit_price_usd set (invalid)",
			input: contracts.ProposedAction{
				ActionID:      "action_777",
				SessionID:     "session_xyz",
				Type:          contracts.ActionTypeTrade,
				Ticker:        "AAPL",
				Side:          contracts.ActionSideBuy,
				Quantity:      15,
				OrderType:     contracts.OrderTypeMarket,
				LimitPriceUSD: ptrFloat64(150),
				Rationale:     "Rebalancing portfolio.",
				IPSVersionReferenced: contracts.IPSVersionRef{
					IPSID:   "ips_111",
					Version: 2,
				},
				ProposedBySkillVersion: contracts.SkillVersionRef{
					SkillName:    "action-drafting",
					SkillVersion: "0.1.0",
				},
				Status:    contracts.ActionStatusDrafted,
				CreatedAt: now,
			},
			expectedValid: false,
			expectTrade:   true,
		},
		{
			name: "Invalid side enum (invalid)",
			input: contracts.ProposedAction{
				ActionID:  "action_777",
				SessionID: "session_xyz",
				Type:      contracts.ActionTypeTrade,
				Ticker:    "AAPL",
				Side:      contracts.ActionSide("hold"),
				Quantity:  15,
				OrderType: contracts.OrderTypeMarket,
				Rationale: "Holding position.",
				IPSVersionReferenced: contracts.IPSVersionRef{
					IPSID:   "ips_111",
					Version: 2,
				},
				ProposedBySkillVersion: contracts.SkillVersionRef{
					SkillName:    "action-drafting",
					SkillVersion: "0.1.0",
				},
				Status:    contracts.ActionStatusDrafted,
				CreatedAt: now,
			},
			expectedValid: false,
			expectTrade:   true,
		},
		{
			name: "Invalid order_type enum (invalid)",
			input: contracts.ProposedAction{
				ActionID:  "action_777",
				SessionID: "session_xyz",
				Type:      contracts.ActionTypeTrade,
				Ticker:    "AAPL",
				Side:      contracts.ActionSideBuy,
				Quantity:  15,
				OrderType: contracts.OrderType("stop_loss"),
				Rationale: "Holding position.",
				IPSVersionReferenced: contracts.IPSVersionRef{
					IPSID:   "ips_111",
					Version: 2,
				},
				ProposedBySkillVersion: contracts.SkillVersionRef{
					SkillName:    "action-drafting",
					SkillVersion: "0.1.0",
				},
				Status:    contracts.ActionStatusDrafted,
				CreatedAt: now,
			},
			expectedValid: false,
			expectTrade:   true,
		},
		{
			name: "Invalid status enum (invalid)",
			input: contracts.ProposedAction{
				ActionID:  "action_777",
				SessionID: "session_xyz",
				Type:      contracts.ActionTypeTrade,
				Ticker:    "AAPL",
				Side:      contracts.ActionSideBuy,
				Quantity:  15,
				OrderType: contracts.OrderTypeMarket,
				Rationale: "Holding position.",
				IPSVersionReferenced: contracts.IPSVersionRef{
					IPSID:   "ips_111",
					Version: 2,
				},
				ProposedBySkillVersion: contracts.SkillVersionRef{
					SkillName:    "action-drafting",
					SkillVersion: "0.1.0",
				},
				Status:    contracts.ActionStatus("processing"),
				CreatedAt: now,
			},
			expectedValid: false,
			expectTrade:   true,
		},
		{
			name: "Negative estimated_price_usd (invalid)",
			input: contracts.ProposedAction{
				ActionID:          "action_777",
				SessionID:         "session_xyz",
				Type:              contracts.ActionTypeTrade,
				Ticker:            "AAPL",
				Side:              contracts.ActionSideBuy,
				Quantity:          15,
				OrderType:         contracts.OrderTypeMarket,
				EstimatedPriceUSD: ptrFloat64(-10),
				Rationale:         "Rebalancing portfolio.",
				IPSVersionReferenced: contracts.IPSVersionRef{
					IPSID:   "ips_111",
					Version: 2,
				},
				ProposedBySkillVersion: contracts.SkillVersionRef{
					SkillName:    "action-drafting",
					SkillVersion: "0.1.0",
				},
				Status:    contracts.ActionStatusDrafted,
				CreatedAt: now,
			},
			expectedValid: false,
			expectTrade:   true,
		},
		{
			name: "Negative estimated_value_usd (invalid)",
			input: contracts.ProposedAction{
				ActionID:          "action_777",
				SessionID:         "session_xyz",
				Type:              contracts.ActionTypeTrade,
				Ticker:            "AAPL",
				Side:              contracts.ActionSideBuy,
				Quantity:          15,
				OrderType:         contracts.OrderTypeMarket,
				EstimatedValueUSD: ptrFloat64(-150),
				Rationale:         "Rebalancing portfolio.",
				IPSVersionReferenced: contracts.IPSVersionRef{
					IPSID:   "ips_111",
					Version: 2,
				},
				ProposedBySkillVersion: contracts.SkillVersionRef{
					SkillName:    "action-drafting",
					SkillVersion: "0.1.0",
				},
				Status:    contracts.ActionStatusDrafted,
				CreatedAt: now,
			},
			expectedValid: false,
			expectTrade:   true,
		},
		{
			name: "Missing ActionID (invalid)",
			input: contracts.ProposedAction{
				ActionID:  "",
				SessionID: "session_abc",
				Type:      contracts.ActionTypeTrade,
			},
			expectedValid: false,
			expectTrade:   true,
		},
		{
			name: "Zero quantity (invalid)",
			input: contracts.ProposedAction{
				ActionID:  "action_888",
				SessionID: "session_abc",
				Type:      contracts.ActionTypeTrade,
				Ticker:    "MSFT",
				Side:      contracts.ActionSideSell,
				Quantity:  0,
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
