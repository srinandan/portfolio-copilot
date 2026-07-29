package contracts

import (
	"time"
)

// RuleResult represents the verdict/outcome of a single checked compliance rule.
type RuleResult struct {
	RuleID      string  `json:"rule_id" firestore:"rule_id"`
	Description string  `json:"description" firestore:"description"`
	Passed      bool    `json:"passed" firestore:"passed"`
	Detail      *string `json:"detail,omitempty" firestore:"detail,omitempty"`
}

// ReviewerVerdict represents the validation and risk policy compliance report from the Reviewer/Critic.
type ReviewerVerdict struct {
	VerdictID                string          `json:"verdict_id" firestore:"verdict_id"`
	ActionID                 string          `json:"action_id" firestore:"action_id"`
	IPSVersionCheckedAgainst IPSVersionRef   `json:"ips_version_checked_against" firestore:"ips_version_checked_against"`
	RuleResults              []RuleResult    `json:"rule_results" firestore:"rule_results"`
	OverallPass              bool            `json:"overall_pass" firestore:"overall_pass"`
	RequiresHumanApproval    bool            `json:"requires_human_approval" firestore:"requires_human_approval"`
	ReviewerSkillVersion     SkillVersionRef `json:"reviewer_skill_version" firestore:"reviewer_skill_version"`
	ReviewedAt               time.Time       `json:"reviewed_at" firestore:"reviewed_at"`
}

// Validate returns true if the ReviewerVerdict meets basic validation rules.
func (v *ReviewerVerdict) Validate() bool {
	if v.VerdictID == "" || v.ActionID == "" || v.ReviewedAt.IsZero() {
		return false
	}
	if v.IPSVersionCheckedAgainst.IPSID == "" || v.IPSVersionCheckedAgainst.Version < 1 {
		return false
	}
	if v.ReviewerSkillVersion.SkillName == "" || v.ReviewerSkillVersion.SkillVersion == "" {
		return false
	}
	if len(v.RuleResults) == 0 {
		return false
	}
	for _, rule := range v.RuleResults {
		if rule.RuleID == "" || rule.Description == "" {
			return false
		}
	}
	return true
}
