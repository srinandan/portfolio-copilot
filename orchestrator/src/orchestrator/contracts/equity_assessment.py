"""Contract for the standalone equity assessment produced by the equity-research skill.

`EquityAssessment` is the *security-only* view — "is this name attractive on its
own merits?" — independent of any user. It is transient (like DriftReport /
ResearchBrief): computed and consumed within a planning cycle, not a persisted,
audited artifact. The downstream `suitability` skill combines it with the user's
IPS/holdings to produce an advisory `EquityRecommendation`.

All figures are advisory and model-derived; nothing here is investment advice.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from .research_brief import ConfidenceLevel


class ValuationVerdict(str, Enum):
    """Standalone valuation lean derived from intrinsic value vs. market price."""

    UNDERVALUED = "undervalued"
    FAIRLY_VALUED = "fairly_valued"
    OVERVALUED = "overvalued"
    UNKNOWN = "unknown"


class DcfResult(BaseModel):
    """Outputs of the discounted-cash-flow model and the assumptions behind them."""

    intrinsic_value_per_share_usd: Optional[float] = Field(
        default=None, description="DCF-derived intrinsic equity value per share."
    )
    current_price_usd: Optional[float] = Field(default=None, description="Latest market price used for comparison.")
    upside_pct: Optional[float] = Field(
        default=None, description="(intrinsic - price) / price * 100; positive means undervalued."
    )
    enterprise_value_usd: Optional[float] = Field(default=None, description="Sum of discounted FCF plus terminal value.")
    equity_value_usd: Optional[float] = Field(default=None, description="Enterprise value less net debt.")
    net_debt_usd: Optional[float] = Field(default=None, description="Total debt less cash and equivalents.")

    base_fcf_usd: Optional[float] = Field(default=None, description="Starting free cash flow projected forward.")
    fcf_growth_rate: float = Field(description="Annual FCF growth rate applied during the projection window.")
    discount_rate: float = Field(description="Discount rate (WACC proxy) used to present-value cash flows.")
    terminal_growth_rate: float = Field(description="Perpetual growth rate used for the terminal value.")
    projection_years: int = Field(description="Number of years of explicit FCF projection.")


class QualityMetrics(BaseModel):
    """Fundamental quality ratios from the latest annual period (all optional)."""

    net_margin_pct: Optional[float] = Field(default=None, description="Net income / revenue * 100.")
    fcf_margin_pct: Optional[float] = Field(default=None, description="Free cash flow / revenue * 100.")
    revenue_cagr_pct: Optional[float] = Field(
        default=None, description="Compound annual revenue growth across available annual periods."
    )
    return_on_equity_pct: Optional[float] = Field(default=None, description="Net income / total equity * 100.")
    debt_to_equity: Optional[float] = Field(default=None, description="Total debt / total equity.")


class TradingMultiples(BaseModel):
    """The subject's own trading multiples (peer comps can extend this later)."""

    market_cap_usd: Optional[float] = Field(default=None, description="Price * shares outstanding.")
    price_to_earnings: Optional[float] = Field(default=None, description="Price / diluted EPS.")
    price_to_fcf: Optional[float] = Field(default=None, description="Market cap / free cash flow.")
    ev_to_operating_income: Optional[float] = Field(
        default=None, description="Enterprise value / operating income (EBIT proxy)."
    )


class EquityAssessment(BaseModel):
    """Standalone, user-independent assessment of a single equity."""

    ticker: str = Field(description="Uppercase ticker symbol.")
    company_name: Optional[str] = Field(default=None, description="Company / registrant name.")
    as_of: datetime = Field(description="UTC timestamp when the assessment was computed.")
    data_source: str = Field(description="Origin of the underlying fundamentals (e.g. 'sec_edgar', 'mock').")

    dcf: Optional[DcfResult] = Field(default=None, description="DCF valuation, when enough data was available.")
    quality: Optional[QualityMetrics] = Field(default=None, description="Fundamental quality ratios.")
    multiples: Optional[TradingMultiples] = Field(default=None, description="Trading multiples for the subject.")

    valuation_verdict: ValuationVerdict = Field(
        default=ValuationVerdict.UNKNOWN, description="Standalone valuation lean."
    )
    confidence: ConfidenceLevel = Field(
        default=ConfidenceLevel.LOW, description="Confidence in the assessment given data completeness."
    )

    key_drivers: list[str] = Field(default_factory=list, description="Factual, model-derived supportive points.")
    key_risks: list[str] = Field(default_factory=list, description="Factual, model-derived risk points.")
    disclaimers: list[str] = Field(
        default_factory=list, description="Advisory disclaimers; this is not investment advice."
    )
