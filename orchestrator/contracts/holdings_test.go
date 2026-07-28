package contracts_test

import (
	"encoding/json"
	"reflect"
	"testing"
	"time"

	"orchestrator/contracts"
)

func TestHoldingsSnapshotRoundTripAndValidation(t *testing.T) {
	now := time.Now().UTC().Truncate(time.Second)

	accountTypeTaxable := contracts.AccountTypeTaxable
	accountTypeRetirement := contracts.AccountTypeRetirement
	accountTypeInvalid := contracts.AccountType("invalid_type")

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
						AccountType:    &accountTypeTaxable,
					},
					{
						Ticker:         "BND",
						Quantity:       100,
						AssetClass:     "bonds",
						MarketValueUSD: 7200,
						AccountType:    &accountTypeRetirement,
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
			name: "Position with invalid account type (invalid)",
			input: contracts.HoldingsSnapshot{
				UserID: "user_123",
				AsOf:   now,
				Positions: []contracts.Position{
					{
						Ticker:         "AAPL",
						Quantity:       5,
						AssetClass:     "equity",
						MarketValueUSD: 100,
						AccountType:    &accountTypeInvalid,
					},
				},
			},
			expectedValid: false,
		},
		{
			name: "Negative cash_usd (invalid)",
			input: contracts.HoldingsSnapshot{
				UserID: "user_123",
				AsOf:   now,
				Positions: []contracts.Position{
					{
						Ticker:         "AAPL",
						Quantity:       5,
						AssetClass:     "equity",
						MarketValueUSD: 100,
					},
				},
				CashUSD: ptrFloat64(-50),
			},
			expectedValid: false,
		},
		{
			name: "Negative total_value_usd (invalid)",
			input: contracts.HoldingsSnapshot{
				UserID: "user_123",
				AsOf:   now,
				Positions: []contracts.Position{
					{
						Ticker:         "AAPL",
						Quantity:       5,
						AssetClass:     "equity",
						MarketValueUSD: 100,
					},
				},
				TotalValueUSD: ptrFloat64(-1000),
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

				var actual contracts.HoldingsSnapshot
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
