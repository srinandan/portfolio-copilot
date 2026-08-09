package contracts

import (
	"time"
)

// ActorType defines allowed categories of actors in audit events.
type ActorType string

const (
	ActorTypeAgent ActorType = "agent"
	ActorTypeHuman ActorType = "human"
)

// AuditEventType defines allowed governance-relevant audit event types.
type AuditEventType string

const (
	AuditEventSkillInvoked          AuditEventType = "skill_invoked"
	AuditEventSkillInvocationFailed AuditEventType = "skill_invocation_failed"
	AuditEventSkillRevoked          AuditEventType = "skill_revoked"
	AuditEventIPSCreated            AuditEventType = "ips_created"
	AuditEventIPSSuperseded         AuditEventType = "ips_superseded"
	AuditEventActionProposed        AuditEventType = "action_proposed"
	AuditEventReviewCompleted       AuditEventType = "review_completed"
	AuditEventApprovalRequested     AuditEventType = "approval_requested"
	AuditEventApprovalGranted       AuditEventType = "approval_granted"
	AuditEventApprovalRejected      AuditEventType = "approval_rejected"
	AuditEventActionExecuted        AuditEventType = "action_executed"
	AuditEventActionFailed          AuditEventType = "action_failed"
	AuditEventReviewerBypassed      AuditEventType = "reviewer_bypassed"
)

// ActorRef represents the agent or human actor responsible for the audit event.
type ActorRef struct {
	Type            ActorType `json:"type" firestore:"type"` // agent, human
	UserID          *string   `json:"user_id,omitempty" firestore:"user_id,omitempty"`
	SkillName       *string   `json:"skill_name,omitempty" firestore:"skill_name,omitempty"`
	SkillVersion    *string   `json:"skill_version,omitempty" firestore:"skill_version,omitempty"`
	RegistryEntryID *string   `json:"registry_entry_id,omitempty" firestore:"registry_entry_id,omitempty"`
	ApprovalScope   *string   `json:"approval_scope,omitempty" firestore:"approval_scope,omitempty"`
}

// AuditLogEntry represents one entry per governance-relevant event.
type AuditLogEntry struct {
	LogID             string         `json:"log_id" firestore:"log_id"`
	EventType         AuditEventType `json:"event_type" firestore:"event_type"` // skill_invoked, skill_invocation_failed, skill_revoked, ips_created, ips_superseded, action_proposed, review_completed, approval_requested, approval_granted, approval_rejected, action_executed, action_failed, reviewer_bypassed
	Timestamp         time.Time      `json:"timestamp" firestore:"timestamp"`
	Actor             ActorRef       `json:"actor" firestore:"actor"`
	RelatedActionID   *string        `json:"related_action_id,omitempty" firestore:"related_action_id,omitempty"`
	RelatedIPSVersion *IPSVersionRef `json:"related_ips_version,omitempty" firestore:"related_ips_version,omitempty"`
	Detail            *string        `json:"detail,omitempty" firestore:"detail,omitempty"`
}

// Validate returns true if the AuditLogEntry meets basic validation rules.
func (ale *AuditLogEntry) Validate() bool {
	if ale.LogID == "" || ale.Timestamp.IsZero() {
		return false
	}
	switch ale.EventType {
	case AuditEventSkillInvoked, AuditEventSkillInvocationFailed, AuditEventSkillRevoked, AuditEventIPSCreated, AuditEventIPSSuperseded, AuditEventActionProposed, AuditEventReviewCompleted, AuditEventApprovalRequested, AuditEventApprovalGranted, AuditEventApprovalRejected, AuditEventActionExecuted, AuditEventActionFailed, AuditEventReviewerBypassed:
	default:
		return false
	}
	switch ale.Actor.Type {
	case ActorTypeAgent, ActorTypeHuman:
	default:
		return false
	}
	return true
}
