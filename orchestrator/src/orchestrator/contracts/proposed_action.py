from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from .ips import RelatedIPSVersion


class ActionType(str, Enum):
    TRADE = "trade"


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class SkillVersionRef(BaseModel):
    skill_name: str
    skill_version: str
    registry_entry_id: Optional[str] = None


class ActionStatus(str, Enum):
    DRAFTED = "drafted"
    REVIEWED_PASS = "reviewed_pass"
    REVIEWED_FAIL = "reviewed_fail"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"


class ProposedAction(BaseModel):
    action_id: str
    session_id: str
    type: ActionType
    ticker: str
    side: Side
    quantity: float = Field(gt=0)
    order_type: OrderType
    limit_price_usd: Optional[float] = None
    estimated_price_usd: float = Field(gt=0)
    estimated_value_usd: float = Field(gt=0)
    rationale: str
    supporting_research_refs: List[str] = Field(default_factory=list)
    ips_version_referenced: RelatedIPSVersion
    proposed_by_skill_version: SkillVersionRef
    status: ActionStatus
    created_at: datetime
