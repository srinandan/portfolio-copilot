package contracts

import (
	"time"
)

// LiabilityType defines the allowed categories of liabilities.
type LiabilityType string

const (
	LiabilityTypeCreditCard  LiabilityType = "credit_card"
	LiabilityTypeMortgage    LiabilityType = "mortgage"
	LiabilityTypeAutoLoan    LiabilityType = "auto_loan"
	LiabilityTypeStudentLoan LiabilityType = "student_loan"
	LiabilityTypeHELOC       LiabilityType = "heloc"
	LiabilityTypeOther       LiabilityType = "other"
)

// Liability represents a single debt entry in LiabilitiesSnapshot.
type Liability struct {
	LiabilityID         string        `json:"liability_id"`
	Type                LiabilityType `json:"type"`
	Description         *string       `json:"description,omitempty"`
	BalanceUSD          float64       `json:"balance_usd"`
	InterestRatePercent *float64      `json:"interest_rate_percent,omitempty"`
	MinimumPaymentUSD   float64       `json:"minimum_payment_usd"`
}

// LiabilitiesSnapshot represents current debts (credit cards, mortgage, other loans).
// Parallel to HoldingsSnapshot — not versioned/append-only.
type LiabilitiesSnapshot struct {
	UserID              string      `json:"user_id"`
	AsOf                time.Time   `json:"as_of"`
	Liabilities         []Liability `json:"liabilities"`
	TotalLiabilitiesUSD *float64    `json:"total_liabilities_usd,omitempty"`
}

// Validate returns true if the liabilities snapshot meets basic validation rules.
func (l *LiabilitiesSnapshot) Validate() bool {
	if l.UserID == "" || l.AsOf.IsZero() {
		return false
	}
	for _, liab := range l.Liabilities {
		if liab.LiabilityID == "" || liab.BalanceUSD < 0 || liab.MinimumPaymentUSD < 0 {
			return false
		}
		switch liab.Type {
		case LiabilityTypeCreditCard, LiabilityTypeMortgage, LiabilityTypeAutoLoan, LiabilityTypeStudentLoan, LiabilityTypeHELOC, LiabilityTypeOther:
		default:
			return false
		}
		if liab.InterestRatePercent != nil && *liab.InterestRatePercent < 0 {
			return false
		}
	}
	if l.TotalLiabilitiesUSD != nil && *l.TotalLiabilitiesUSD < 0 {
		return false
	}
	return true
}

