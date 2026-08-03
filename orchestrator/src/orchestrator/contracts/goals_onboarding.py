"""Contract for the Goals Onboarding Managed Agent output."""

from typing import List, Optional

from pydantic import BaseModel, Field

from .ips import Constraints, Goal, LiquidityNeeds, RebalancingRules, RiskTolerance, TargetAllocation
from .liabilities import Liability


class GoalsOnboardingResult(BaseModel):
    """Structured result produced by the Goals Onboarding Managed Agent interview."""
    user_id: str = Field(description="User identifier.")
    primary_goal: Optional[Goal] = Field(default=None, description="Primary financial goal synthesized from interview.")
    additional_goals: List[Goal] = Field(default_factory=list, description="Additional financial goals.")
    risk_tolerance: RiskTolerance = Field(description="Synthesized risk tolerance tier.")
    time_horizon_years: int = Field(description="Investment time horizon in years.")
    target_allocation: List[TargetAllocation] = Field(description="Target asset class allocation bands.")
    constraints: Optional[Constraints] = Field(default=None, description="Investment constraints (e.g. excluded sectors/tickers).")
    liquidity_needs: Optional[LiquidityNeeds] = Field(default=None, description="Liquidity reserve requirements.")
    rebalancing_rules: Optional[RebalancingRules] = Field(default=None, description="Rebalancing threshold rules.")
    identified_liabilities: List[Liability] = Field(default_factory=list, description="Liabilities identified during interview.")
    interview_summary: str = Field(description="Natural language summary of user goals and onboarding outcome.")
