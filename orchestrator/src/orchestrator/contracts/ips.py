import re
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


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

    @model_validator(mode="after")
    def sanitize_constraints(self) -> "Constraints":
        self.excluded_tickers = [t.strip().upper() for t in self.excluded_tickers if t and t.strip()]
        self.excluded_sectors = [s.strip() for s in self.excluded_sectors if s and s.strip()]
        return self


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
    effective_date: date
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

    @field_validator("user_id")
    @classmethod
    def check_user_id(cls, v: str) -> str:
        trimmed = str(v).strip()
        if not re.match(r"^[a-zA-Z0-9_-]{1,64}$", trimmed):
            raise ValueError(f"Invalid user_id format: {v!r}")
        return trimmed


class RelatedIPSVersion(BaseModel):
    ips_id: str
    version: int
