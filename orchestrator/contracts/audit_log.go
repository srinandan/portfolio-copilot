package contracts

import (
	"time"
)

// ActorRef represents the agent or human actor responsible for the audit event.
type ActorRef struct {
	Type            string  `json:"type"` // agent, human
	UserID          *string `json:"user_id,omitempty"`
	SkillName       *string `json:"skill_name,omitempty"`
	SkillVersion    *string `json:"skill_version,omitempty"`
	RegistryEntryID *string `json:"registry_entry_id,omitempty"`
	ApprovalScope   *string `json:"approval_scope,omitempty"`
}

// AuditLogEntry represents one entry per governance-relevant event.
type AuditLogEntry struct {
	LogID             string         `json:"log_id"`
	EventType         string         `json:"event_type"` // skill_invoked, skill_revoked, ips_created, ips_superseded, action_proposed, review_completed, approval_requested, approval_granted, approval_rejected, action_executed, action_failed
	Timestamp         time.Time      `json:"timestamp"`
	Actor             ActorRef       `json:"actor"`
	RelatedActionID   *string        `json:"related_action_id,omitempty"`
	RelatedIPSVersion *IPSVersionRef `json:"related_ips_version,omitempty"`
	Detail            *string        `json:"detail,omitempty"`
}

// Validate returns true if the AuditLogEntry meets basic validation rules.
func (ale *AuditLogEntry) Validate() bool {
	if ale.LogID == "" || ale.EventType == "" || ale.Timestamp.IsZero() || ale.Actor.Type == "" {
		return false
	}
	return true
}
