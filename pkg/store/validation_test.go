package store

import (
	"testing"
	"time"

	"portfolio-copilot/orchestrator/contracts"
)

// We can test validation completely offline without a Firestore emulator.
// c.fs will be nil, but validate() doesn't use it.

func getTestClient(t *testing.T) *Client {
	t.Helper()
	c := &Client{}
	if err := c.loadSchemas(); err != nil {
		t.Fatalf("failed to load schemas: %v", err)
	}
	return c
}

func ptrFloat64(f float64) *float64 { return &f }

func TestIPSValidation(t *testing.T) {
	c := getTestClient(t)

	tests := []struct {
		name    string
		ips     *contracts.InvestmentPolicyStatement
		wantErr bool
	}{
		{
			name: "valid IPS (golden path)",
			ips: &contracts.InvestmentPolicyStatement{
				IPSID:            "user123_ips",
				UserID:           "user123",
				Version:          1,
				Status:           contracts.IPSStatusActive,
				EffectiveDate:    "2023-10-01",
				RiskTolerance:    contracts.RiskToleranceModerate,
				TimeHorizonYears: 10,
				TargetAllocation: []contracts.AllocationBand{
					{AssetClass: "equity", TargetPercent: 60, MinPercent: 50, MaxPercent: 70},
					{AssetClass: "bonds", TargetPercent: 30, MinPercent: 20, MaxPercent: 40},
					{AssetClass: "cash", TargetPercent: 10, MinPercent: 5, MaxPercent: 15},
				},
				Constraints: contracts.Constraints{
					ConcentrationLimitPercent: 15,
				},
				CreatedAt: time.Date(2023, 10, 1, 10, 0, 0, 0, time.UTC),
			},
			wantErr: false,
		},
		{
			name: "invalid risk tolerance (not in enum)",
			ips: &contracts.InvestmentPolicyStatement{
				IPSID:            "user123_ips",
				UserID:           "user123",
				Version:          1,
				Status:           contracts.IPSStatusActive,
				EffectiveDate:    "2023-10-01",
				RiskTolerance:    "SUPER_AGGRESSIVE", // Invalid
				TimeHorizonYears: 10,
				TargetAllocation: []contracts.AllocationBand{
					{AssetClass: "equity", TargetPercent: 60, MinPercent: 50, MaxPercent: 70},
				},
				Constraints: contracts.Constraints{
					ConcentrationLimitPercent: 15,
				},
				CreatedAt: time.Date(2023, 10, 1, 10, 0, 0, 0, time.UTC),
			},
			wantErr: true,
		},
		{
			name: "missing required fields",
			ips: &contracts.InvestmentPolicyStatement{
				IPSID:   "user123_ips",
				Version: 1,
				// Missing UserID, Status, RiskTolerance, etc.
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := validate(c.ipsSchema, tt.ips)
			if (err != nil) != tt.wantErr {
				t.Errorf("validate() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestHoldingsValidation(t *testing.T) {
	c := getTestClient(t)

	tests := []struct {
		name    string
		h       *contracts.HoldingsSnapshot
		wantErr bool
	}{
		{
			name: "valid holdings",
			h: &contracts.HoldingsSnapshot{
				UserID: "user123",
				AsOf:   time.Date(2023, 10, 1, 10, 0, 0, 0, time.UTC),
				Positions: []contracts.Position{
					{Ticker: "AAPL", Quantity: 10, AssetClass: "equity", MarketValueUSD: 1500},
				},
			},
			wantErr: false,
		},
		{
			name: "negative quantity",
			h: &contracts.HoldingsSnapshot{
				UserID: "user123",
				AsOf:   time.Date(2023, 10, 1, 10, 0, 0, 0, time.UTC),
				Positions: []contracts.Position{
					{Ticker: "AAPL", Quantity: -10, AssetClass: "equity", MarketValueUSD: 1500},
				},
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := validate(c.holdingsSchema, tt.h)
			if (err != nil) != tt.wantErr {
				t.Errorf("validate() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}
