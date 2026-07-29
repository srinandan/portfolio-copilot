package contracts_test

import (
	"encoding/json"
	"reflect"
	"testing"
	"time"

	"portfolio-copilot/orchestrator/contracts"
)

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
		{
			name: "Invalid liability type enum (invalid)",
			input: contracts.LiabilitiesSnapshot{
				UserID: "user_789",
				AsOf:   now,
				Liabilities: []contracts.Liability{
					{
						LiabilityID:       "liab_01",
						Type:              contracts.LiabilityType("payday_loan"),
						BalanceUSD:        50,
						MinimumPaymentUSD: 10,
					},
				},
			},
			expectedValid: false,
		},
		{
			name: "Negative interest rate percent (invalid)",
			input: contracts.LiabilitiesSnapshot{
				UserID: "user_789",
				AsOf:   now,
				Liabilities: []contracts.Liability{
					{
						LiabilityID:         "liab_01",
						Type:                contracts.LiabilityTypeCreditCard,
						BalanceUSD:          500,
						MinimumPaymentUSD:   25,
						InterestRatePercent: ptrFloat64(-5.5),
					},
				},
			},
			expectedValid: false,
		},
		{
			name: "Negative total_liabilities_usd (invalid)",
			input: contracts.LiabilitiesSnapshot{
				UserID: "user_789",
				AsOf:   now,
				Liabilities: []contracts.Liability{
					{
						LiabilityID:       "liab_01",
						Type:              contracts.LiabilityTypeCreditCard,
						BalanceUSD:        500,
						MinimumPaymentUSD: 25,
					},
				},
				TotalLiabilitiesUSD: ptrFloat64(-100),
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
