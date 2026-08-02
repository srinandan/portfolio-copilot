from datetime import datetime
from enum import Enum
from typing import Optional

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
    user_id: Optional[str] = None
    skill_name: Optional[str] = None
    skill_version: Optional[str] = None
    registry_entry_id: Optional[str] = None
    approval_scope: Optional[str] = None


class RelatedIPSVersion(BaseModel):
    ips_id: str
    version: int


class AuditLogEntry(BaseModel):
    log_id: str
    event_type: EventType
    timestamp: datetime
    actor: Actor
    related_action_id: Optional[str] = None
    related_ips_version: Optional[RelatedIPSVersion] = None
    detail: Optional[str] = None
