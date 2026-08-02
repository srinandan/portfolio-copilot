from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class EventType(str, Enum):
    SKILL_INVOKED = "skill_invoked"
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


class ActorType(str, Enum):
    AGENT = "agent"
    HUMAN = "human"


class Actor(BaseModel):
    type: ActorType
    user_id: str | None = None
    skill_name: str | None = None
    skill_version: str | None = None
    registry_entry_id: str | None = None
    approval_scope: str | None = None


class RelatedIPSVersion(BaseModel):
    ips_id: str
    version: int


class AuditLogEntry(BaseModel):
    log_id: str
    event_type: EventType
    timestamp: datetime
    actor: Actor
    related_action_id: str | None = None
    related_ips_version: RelatedIPSVersion | None = None
    detail: str | None = None
