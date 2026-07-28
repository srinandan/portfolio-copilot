package contracts

import (
	"time"
)

// Position represents a single portfolio position holding in HoldingsSnapshot.
type Position struct {
	Ticker         string   `json:"ticker"`
	Quantity       float64  `json:"quantity"`
	AssetClass     string   `json:"asset_class"`
	MarketValueUSD float64  `json:"market_value_usd"`
	AccountType    *string  `json:"account_type,omitempty"` // taxable, retirement
}

// HoldingsSnapshot represents current portfolio holdings.
// Unlike the IPS, this is current-state data — overwritten as holdings change, not versioned/append-only.
type HoldingsSnapshot struct {
	UserID        string     `json:"user_id"`
	AsOf          time.Time  `json:"as_of"`
	Positions     []Position `json:"positions"`
	CashUSD       *float64   `json:"cash_usd,omitempty"`
	TotalValueUSD *float64   `json:"total_value_usd,omitempty"`
}

// Validate returns true if the snapshot meets basic validation rules.
func (h *HoldingsSnapshot) Validate() bool {
	if h.UserID == "" || h.AsOf.IsZero() {
		return false
	}
	for _, pos := range h.Positions {
		if pos.Ticker == "" || pos.Quantity < 0 || pos.AssetClass == "" || pos.MarketValueUSD < 0 {
			return false
		}
	}
	return true
}
