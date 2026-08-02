from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from .ips import RelatedIPSVersion
from .proposed_action import SkillVersionRef


class RuleResult(BaseModel):
    rule_id: str
    description: str
    passed: bool
    detail: Optional[str] = None


class ReviewerVerdict(BaseModel):
    verdict_id: str
    action_id: str
    ips_version_checked_against: RelatedIPSVersion
    rule_results: List[RuleResult] = Field(min_length=1)
    overall_pass: bool
    requires_human_approval: bool
    reviewer_skill_version: SkillVersionRef
    reviewed_at: datetime
