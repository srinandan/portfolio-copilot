package contracts

import (
	"time"
)

// ActionType defines allowed types of proposed actions (narrowly restricted to trade in this version).
type ActionType string

const (
	ActionTypeTrade ActionType = "trade"
)

// ActionSide defines trade sides.
type ActionSide string

const (
	ActionSideBuy  ActionSide = "buy"
	ActionSideSell ActionSide = "sell"
)

// OrderType defines trade order types.
type OrderType string

const (
	OrderTypeMarket OrderType = "market"
	OrderTypeLimit  OrderType = "limit"
)

// ActionStatus defines lifecycle status values for a ProposedAction.
type ActionStatus string

const (
	ActionStatusDrafted         ActionStatus = "drafted"
	ActionStatusReviewedPass    ActionStatus = "reviewed_pass"
	ActionStatusReviewedFail    ActionStatus = "reviewed_fail"
	ActionStatusPendingApproval ActionStatus = "pending_approval"
	ActionStatusApproved        ActionStatus = "approved"
	ActionStatusRejected        ActionStatus = "rejected"
	ActionStatusExecuted        ActionStatus = "executed"
	ActionStatusFailed          ActionStatus = "failed"
)

// IPSVersionRef refers to a specific version of an InvestmentPolicyStatement.
type IPSVersionRef struct {
	IPSID   string `json:"ips_id" firestore:"ips_id"`
	Version int    `json:"version" firestore:"version"`
}

// SkillVersionRef refers to a specific registered skill and version.
type SkillVersionRef struct {
	SkillName       string  `json:"skill_name" firestore:"skill_name"`
	SkillVersion    string  `json:"skill_version" firestore:"skill_version"`
	RegistryEntryID *string `json:"registry_entry_id,omitempty" firestore:"registry_entry_id,omitempty"`
}

// ProposedAction represents a proposed investment or trade.
// What Action Drafting produces, the Reviewer validates, and a human approves/rejects.
type ProposedAction struct {
	ActionID               string          `json:"action_id" firestore:"action_id"`
	SessionID              string          `json:"session_id" firestore:"session_id"`
	Type                   ActionType      `json:"type" firestore:"type"` // trade
	Ticker                 string          `json:"ticker" firestore:"ticker"`
	Side                   ActionSide      `json:"side" firestore:"side"` // buy, sell
	Quantity               float64         `json:"quantity" firestore:"quantity"`
	OrderType              OrderType       `json:"order_type" firestore:"order_type"` // market, limit
	LimitPriceUSD          *float64        `json:"limit_price_usd,omitempty" firestore:"limit_price_usd,omitempty"`
	EstimatedPriceUSD      *float64        `json:"estimated_price_usd,omitempty" firestore:"estimated_price_usd,omitempty"`
	EstimatedValueUSD      *float64        `json:"estimated_value_usd,omitempty" firestore:"estimated_value_usd,omitempty"`
	Rationale              string          `json:"rationale" firestore:"rationale"`
	SupportingResearchRefs []string        `json:"supporting_research_refs,omitempty" firestore:"supporting_research_refs,omitempty"`
	IPSVersionReferenced   IPSVersionRef   `json:"ips_version_referenced" firestore:"ips_version_referenced"`
	ProposedBySkillVersion SkillVersionRef `json:"proposed_by_skill_version" firestore:"proposed_by_skill_version"`
	Status                 ActionStatus    `json:"status" firestore:"status"` // drafted, reviewed_pass, reviewed_fail, pending_approval, approved, rejected, executed, failed
	CreatedAt              time.Time       `json:"created_at" firestore:"created_at"`
}

// IsTrade returns true if the action type is a trade.
func (pa *ProposedAction) IsTrade() bool {
	return pa.Type == ActionTypeTrade
}

// Validate returns true if the ProposedAction meets basic validation rules.
func (pa *ProposedAction) Validate() bool {
	if pa.ActionID == "" || pa.SessionID == "" || pa.Ticker == "" || pa.Rationale == "" || pa.CreatedAt.IsZero() {
		return false
	}
	if pa.Type != ActionTypeTrade {
		return false
	}
	switch pa.Side {
	case ActionSideBuy, ActionSideSell:
	default:
		return false
	}
	switch pa.OrderType {
	case OrderTypeMarket, OrderTypeLimit:
	default:
		return false
	}
	if pa.OrderType == OrderTypeLimit {
		if pa.LimitPriceUSD == nil || *pa.LimitPriceUSD <= 0 {
			return false
		}
	} else {
		if pa.LimitPriceUSD != nil {
			return false
		}
	}
	switch pa.Status {
	case ActionStatusDrafted, ActionStatusReviewedPass, ActionStatusReviewedFail, ActionStatusPendingApproval, ActionStatusApproved, ActionStatusRejected, ActionStatusExecuted, ActionStatusFailed:
	default:
		return false
	}
	if pa.Quantity <= 0 {
		return false
	}
	if pa.EstimatedPriceUSD != nil && *pa.EstimatedPriceUSD <= 0 {
		return false
	}
	if pa.EstimatedValueUSD != nil && *pa.EstimatedValueUSD <= 0 {
		return false
	}
	if pa.IPSVersionReferenced.IPSID == "" || pa.IPSVersionReferenced.Version < 1 {
		return false
	}
	if pa.ProposedBySkillVersion.SkillName == "" || pa.ProposedBySkillVersion.SkillVersion == "" {
		return false
	}
	return true
}
