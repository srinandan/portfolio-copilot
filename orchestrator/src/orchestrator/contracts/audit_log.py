from datetime import datetime
from enum import Enum

from pydantic import BaseModel

from .ips import RelatedIPSVersion


class EventType(str, Enum):
    SKILL_INVOKED = "skill_invoked"
    SKILL_INVOCATION_FAILED = "skill_invocation_failed"
    SKILL_REVOKED = "skill_revoked"
    IPS_CREATED = "ips_created"
    IPS_SUPERSEDED = "ips_superseded"
    ACTION_PROPOSED = "action_proposed"
    REVIEW_COMPLETED = "review_completed"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"
    ACTION_EXECUTED = "action_executed"
    ACTION_FAILED = "action_failed"
    REVIEWER_BYPASSED = "reviewer_bypassed"


class ActorType(str, Enum):
    AGENT = "agent"
    HUMAN = "human"


class Actor(BaseModel):
    """Identifies the entity responsible for an audit log entry.

    - For human actors (APPROVAL_GRANTED, human APPROVAL_REJECTED):
      type = HUMAN, user_id is set, and skill fields are None.
    - For Registry-discovered skills (private-* skills):
      type = AGENT, skill_name, skill_version, registry_entry_id (revision ID),
      and approval_scope (from SKILL.md YAML frontmatter) are all populated.
    - For built-in orchestrator gates (orchestrator-hitl-gate, orchestrator-execution-gate):
      type = AGENT, skill_name is set, skill_version carries the orchestrator package /
      build SHA version, and registry_entry_id = None and approval_scope = None because
      built-in gates are hard-wired workflow nodes rather than Agent Registry-discovered skills.
    """

    type: ActorType
    user_id: str | None = None
    skill_name: str | None = None
    skill_version: str | None = None
    registry_entry_id: str | None = None
    approval_scope: str | None = None


class AuditLogEntry(BaseModel):
    """One immutable entry per governance-relevant event.

    Ensures that every agent decision or state write is traceable to its
    originating skill identity, code version, registry entry, and authorization scope.
    """

    log_id: str
    event_type: EventType
    timestamp: datetime
    actor: Actor
    related_action_id: str | None = None
    related_ips_version: RelatedIPSVersion | None = None
    detail: str | None = None
