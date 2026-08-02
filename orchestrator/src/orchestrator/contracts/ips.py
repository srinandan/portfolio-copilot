from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class IPSStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class RiskTolerance(str, Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class Goal(BaseModel):
    name: str
    target_amount_usd: float = Field(ge=0)
    target_date: date


class LiquidityNeeds(BaseModel):
    reserve_months: Optional[float] = Field(default=None, ge=0)
    known_upcoming_expenses_usd: Optional[float] = Field(default=None, ge=0)


class TargetAllocation(BaseModel):
    asset_class: str
    target_percent: float = Field(ge=0, le=100)
    min_percent: float = Field(ge=0, le=100)
    max_percent: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def check_bands(self) -> "TargetAllocation":
        if not (self.min_percent <= self.target_percent <= self.max_percent):
            raise ValueError("Bands must satisfy min_percent <= target_percent <= max_percent")
        return self


class AccountType(str, Enum):
    TAXABLE = "taxable"
    RETIREMENT = "retirement"


class Constraints(BaseModel):
    excluded_tickers: List[str] = Field(default_factory=list)
    excluded_sectors: List[str] = Field(default_factory=list)
    concentration_limit_percent: float = Field(ge=0, le=100)
    tax_loss_harvesting_enabled: bool = False
    account_type: Optional[AccountType] = None


class TriggerType(str, Enum):
    THRESHOLD = "threshold"
    CALENDAR = "calendar"
    BOTH = "both"


class RebalancingRules(BaseModel):
    trigger_type: Optional[TriggerType] = None
    drift_threshold_percent: Optional[float] = Field(default=None, ge=0)
    rebalancing_frequency_days: Optional[int] = Field(default=None, ge=1)


class InvestmentPolicyStatement(BaseModel):
    ips_id: str
    user_id: str
    version: int = Field(ge=1)
    status: IPSStatus
    superseded_by: Optional[str] = None
    effective_date: date  # Kept as str to match json schema (or date), let's use date and pydantic will handle it
    risk_tolerance: RiskTolerance
    time_horizon_years: int = Field(ge=0)

    goals: Optional[List[Goal]] = None
    liquidity_needs: Optional[LiquidityNeeds] = None

    target_allocation: List[TargetAllocation]
    constraints: Constraints

    rebalancing_rules: Optional[RebalancingRules] = None

    approval_required_above_usd: Optional[float] = Field(default=None, ge=0)
    approval_required_above_percent: Optional[float] = Field(default=None, ge=0, le=100)

    created_at: datetime
    updated_at: Optional[datetime] = None

class RelatedIPSVersion(BaseModel):
    ips_id: str
    version: int
