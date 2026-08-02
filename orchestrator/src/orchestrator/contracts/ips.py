from datetime import date, datetime
from enum import Enum

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
    reserve_months: float | None = Field(default=None, ge=0)
    known_upcoming_expenses_usd: float | None = Field(default=None, ge=0)


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
    excluded_tickers: list[str] = Field(default_factory=list)
    excluded_sectors: list[str] = Field(default_factory=list)
    concentration_limit_percent: float = Field(ge=0, le=100)
    tax_loss_harvesting_enabled: bool = False
    account_type: AccountType | None = None


class TriggerType(str, Enum):
    THRESHOLD = "threshold"
    CALENDAR = "calendar"
    BOTH = "both"


class RebalancingRules(BaseModel):
    trigger_type: TriggerType | None = None
    drift_threshold_percent: float | None = Field(default=None, ge=0)
    rebalancing_frequency_days: int | None = Field(default=None, ge=1)


class InvestmentPolicyStatement(BaseModel):
    ips_id: str
    user_id: str
    version: int = Field(ge=1)
    status: IPSStatus
    superseded_by: str | None = None
    effective_date: date  # Kept as str to match json schema (or date), let's use date and pydantic will handle it
    risk_tolerance: RiskTolerance
    time_horizon_years: int = Field(ge=0)

    goals: list[Goal] | None = None
    liquidity_needs: LiquidityNeeds | None = None

    target_allocation: list[TargetAllocation]
    constraints: Constraints

    rebalancing_rules: RebalancingRules | None = None

    approval_required_above_usd: float | None = Field(default=None, ge=0)
    approval_required_above_percent: float | None = Field(default=None, ge=0, le=100)

    created_at: datetime
    updated_at: datetime | None = None

class RelatedIPSVersion(BaseModel):
    ips_id: str
    version: int
