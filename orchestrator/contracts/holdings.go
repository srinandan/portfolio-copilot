package contracts

import (
	"time"
)

// Position represents a single portfolio position holding in HoldingsSnapshot.
type Position struct {
	Ticker         string       `json:"ticker" firestore:"ticker"`
	Quantity       float64      `json:"quantity" firestore:"quantity"`
	AssetClass     string       `json:"asset_class" firestore:"asset_class"`
	MarketValueUSD float64      `json:"market_value_usd" firestore:"market_value_usd"`
	AccountType    *AccountType `json:"account_type,omitempty" firestore:"account_type,omitempty"` // taxable, retirement
}

// HoldingsSnapshot represents current portfolio holdings.
// Unlike the IPS, this is current-state data — overwritten as holdings change, not versioned/append-only.
type HoldingsSnapshot struct {
	UserID        string     `json:"user_id" firestore:"user_id"`
	AsOf          time.Time  `json:"as_of" firestore:"as_of"`
	Positions     []Position `json:"positions" firestore:"positions"`
	CashUSD       *float64   `json:"cash_usd,omitempty" firestore:"cash_usd,omitempty"`
	TotalValueUSD *float64   `json:"total_value_usd,omitempty" firestore:"total_value_usd,omitempty"`
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
		if pos.AccountType != nil {
			switch *pos.AccountType {
			case AccountTypeTaxable, AccountTypeRetirement:
			default:
				return false
			}
		}
	}
	if h.CashUSD != nil && *h.CashUSD < 0 {
		return false
	}
	if h.TotalValueUSD != nil && *h.TotalValueUSD < 0 {
		return false
	}
	return true
}
