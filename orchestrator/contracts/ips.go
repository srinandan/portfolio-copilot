package contracts

import (
	"time"
)

// Goal represents a financial goal in InvestmentPolicyStatement.
type Goal struct {
	Name            string  `json:"name"`
	TargetAmountUSD float64 `json:"target_amount_usd"`
	TargetDate      string  `json:"target_date"` // format: date (e.g., YYYY-MM-DD)
}

// LiquidityNeeds represents liquidity needs of a user.
type LiquidityNeeds struct {
	ReserveMonths            *float64 `json:"reserve_months,omitempty"`
	KnownUpcomingExpensesUSD *float64 `json:"known_upcoming_expenses_usd,omitempty"`
}

// AllocationBand represents a target allocation band for an asset class.
type AllocationBand struct {
	AssetClass    string  `json:"asset_class"`
	TargetPercent float64 `json:"target_percent"`
	MinPercent    float64 `json:"min_percent"`
	MaxPercent    float64 `json:"max_percent"`
}

// Constraints represents constraints on investment policies.
type Constraints struct {
	ExcludedTickers           []string `json:"excluded_tickers,omitempty"`
	ExcludedSectors           []string `json:"excluded_sectors,omitempty"`
	ConcentrationLimitPercent float64  `json:"concentration_limit_percent"`
	TaxLossHarvestingEnabled  *bool    `json:"tax_loss_harvesting_enabled,omitempty"`
	AccountType               *string  `json:"account_type,omitempty"` // taxable, retirement
}

// RebalancingRules represents rules for portfolio rebalancing.
type RebalancingRules struct {
	TriggerType              *string  `json:"trigger_type,omitempty"` // threshold, calendar, both
	DriftThresholdPercent    *float64 `json:"drift_threshold_percent,omitempty"`
	RebalancingFrequencyDays *int     `json:"rebalancing_frequency_days,omitempty"`
}

// InvestmentPolicyStatement represents the reference plan produced by Goals & Onboarding.
// Append-only: a change creates a new version rather than editing in place.
type InvestmentPolicyStatement struct {
	IPSID                        string            `json:"ips_id"`
	UserID                       string            `json:"user_id"`
	Version                      int               `json:"version"`
	Status                       string            `json:"status"` // draft, active, superseded
	SupersededBy                 *string           `json:"superseded_by,omitempty"`
	EffectiveDate                string            `json:"effective_date"` // format: date
	RiskTolerance                string            `json:"risk_tolerance"` // conservative, moderate, aggressive
	TimeHorizonYears             int               `json:"time_horizon_years"`
	Goals                        []Goal            `json:"goals,omitempty"`
	LiquidityNeeds               *LiquidityNeeds   `json:"liquidity_needs,omitempty"`
	TargetAllocation             []AllocationBand  `json:"target_allocation"`
	Constraints                  Constraints       `json:"constraints"`
	RebalancingRules             *RebalancingRules `json:"rebalancing_rules,omitempty"`
	ApprovalRequiredAboveUSD     *float64          `json:"approval_required_above_usd,omitempty"`
	ApprovalRequiredAbovePercent *float64          `json:"approval_required_above_percent,omitempty"`
	CreatedAt                    time.Time         `json:"created_at"`
	UpdatedAt                    *time.Time        `json:"updated_at,omitempty"`
}

// IsActive returns true if the status of the IPS is active.
func (ips *InvestmentPolicyStatement) IsActive() bool {
	return ips.Status == "active"
}

// Validate returns true if the IPS meets basic schema validation rules.
func (ips *InvestmentPolicyStatement) Validate() bool {
	if ips.IPSID == "" || ips.UserID == "" || ips.Status == "" || ips.EffectiveDate == "" || ips.RiskTolerance == "" {
		return false
	}
	if ips.Version < 1 || ips.TimeHorizonYears < 0 {
		return false
	}
	for _, allocation := range ips.TargetAllocation {
		if allocation.AssetClass == "" {
			return false
		}
		if allocation.TargetPercent < 0 || allocation.TargetPercent > 100 {
			return false
		}
		if allocation.MinPercent < 0 || allocation.MinPercent > 100 {
			return false
		}
		if allocation.MaxPercent < 0 || allocation.MaxPercent > 100 {
			return false
		}
	}
	if ips.Constraints.ConcentrationLimitPercent < 0 || ips.Constraints.ConcentrationLimitPercent > 100 {
		return false
	}
	return true
}
