"""Contract for the advisory equity recommendation produced by the suitability skill.

`EquityRecommendation` combines the standalone `EquityAssessment` (is the name
attractive?) with the user's policy and portfolio (is it right *for them*?) into
an advisory lean. It is **advisory only**: it is displayed to the user with
disclaimers and never auto-drafts or executes a trade. Transient, like the Drift
Report — surfaced within a planning cycle, not a persisted artifact.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from .equity_assessment import ValuationVerdict
from .research_brief import ConfidenceLevel


class RecommendationDirection(str, Enum):
    """The advisory lean for the user."""

    BUY = "buy"  # attractive and not currently held — consider initiating
    ADD = "add"  # attractive and already held — consider increasing
    HOLD = "hold"  # no clear action for this user right now
    TRIM = "trim"  # consider reducing an existing position
    AVOID = "avoid"  # not suitable (e.g. overvalued and not held, or excluded)


class SuitabilityFactor(BaseModel):
    """One transparent input into the recommendation."""

    name: str = Field(description="Short identifier for the factor, e.g. 'concentration', 'allocation_room'.")
    detail: str = Field(description="Human-readable explanation of the factor's finding.")
    favorable: Optional[bool] = Field(
        default=None,
        description="True if the factor supports buying/adding, False if it argues against, None if neutral.",
    )


class EquityRecommendation(BaseModel):
    """Advisory recommendation for a single equity, personalized to the user's policy."""

    ticker: str = Field(description="Uppercase ticker symbol.")
    as_of: datetime = Field(description="UTC timestamp when the recommendation was produced.")

    direction: RecommendationDirection = Field(description="The advisory lean.")
    conviction: ConfidenceLevel = Field(description="Confidence in the recommendation.")
    rationale: str = Field(description="One-paragraph synthesis of the standalone view and the suitability factors.")

    # Standalone view carried through from the EquityAssessment.
    valuation_verdict: ValuationVerdict = Field(description="Standalone valuation lean from equity-research.")
    upside_pct: Optional[float] = Field(default=None, description="DCF upside vs. price, when available.")
    assessment_confidence: ConfidenceLevel = Field(description="Confidence of the underlying assessment.")

    # Suitability specifics.
    already_held: bool = Field(default=False, description="Whether the user already holds this ticker.")
    current_weight_pct: float = Field(default=0.0, description="Current position weight as % of portfolio value.")
    concentration_limit_pct: Optional[float] = Field(
        default=None, description="The IPS single-position concentration limit."
    )
    headroom_pct: Optional[float] = Field(
        default=None, description="Remaining room to the concentration limit (limit - current weight)."
    )

    suitability_factors: list[SuitabilityFactor] = Field(
        default_factory=list, description="Transparent factors behind the direction."
    )
    key_risks: list[str] = Field(default_factory=list, description="Risks the user should weigh.")
    disclaimers: list[str] = Field(
        default_factory=list, description="Advisory disclaimers; not investment advice; user decides."
    )
