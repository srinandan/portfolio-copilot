import re
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

# Integrity floor for IPS constraint values (SEC-04, issue #355). The deterministic
# reviewer evaluates every rule against the active IPS, so a permissive-but-valid
# policy (concentration 100, empty bands, allocations that don't sum to 100) turns
# the reviewer into a rubber stamp while still reporting overall_pass. These bounds
# make such a policy non-constructable. Fail closed — reject at construction, never
# clamp — so a corrupted IPS never becomes active regardless of where it came from.
CONCENTRATION_LIMIT_MIN_PERCENT = 5.0
CONCENTRATION_LIMIT_MAX_PERCENT = 50.0
MAX_ALLOCATION_BAND_WIDTH_PERCENT = 50.0
ALLOCATION_SUM_TARGET_PERCENT = 100.0
ALLOCATION_SUM_TOLERANCE_PERCENT = 1.0


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
        if self.max_percent - self.min_percent > MAX_ALLOCATION_BAND_WIDTH_PERCENT:
            raise ValueError(
                f"Allocation band for {self.asset_class!r} is too wide "
                f"({self.min_percent}-{self.max_percent}%): a band wider than "
                f"{MAX_ALLOCATION_BAND_WIDTH_PERCENT:.0f} points can never constrain drift"
            )
        return self


def assert_allocations_sum_to_target(allocations: list["TargetAllocation"]) -> None:
    """Reject an allocation set whose target_percents don't sum to ~100%.

    An incomplete set — or an empty one, which sums to 0 — leaves asset classes
    unbounded, so the reviewer's allocation-band rule never fires for them.
    """
    total = sum(a.target_percent for a in allocations)
    if abs(total - ALLOCATION_SUM_TARGET_PERCENT) > ALLOCATION_SUM_TOLERANCE_PERCENT:
        raise ValueError(
            f"target_allocation target_percent must sum to ~{ALLOCATION_SUM_TARGET_PERCENT:.0f}% "
            f"(got {total:.2f}%)"
        )


class AccountType(str, Enum):
    TAXABLE = "taxable"
    RETIREMENT = "retirement"


class Constraints(BaseModel):
    excluded_tickers: list[str] = Field(default_factory=list)
    excluded_sectors: list[str] = Field(default_factory=list)
    concentration_limit_percent: float
    tax_loss_harvesting_enabled: bool = False
    account_type: AccountType | None = None

    @field_validator("concentration_limit_percent")
    @classmethod
    def check_concentration_limit(cls, v: float) -> float:
        if not (CONCENTRATION_LIMIT_MIN_PERCENT <= v <= CONCENTRATION_LIMIT_MAX_PERCENT):
            raise ValueError(
                "concentration_limit_percent must be between "
                f"{CONCENTRATION_LIMIT_MIN_PERCENT:.0f} and {CONCENTRATION_LIMIT_MAX_PERCENT:.0f} "
                f"to remain a credible guardrail (got {v})"
            )
        return v

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

    @model_validator(mode="after")
    def check_allocation_integrity(self) -> "InvestmentPolicyStatement":
        assert_allocations_sum_to_target(self.target_allocation)
        return self


class RelatedIPSVersion(BaseModel):
    ips_id: str
    version: int
