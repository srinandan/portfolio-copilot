"""Deterministic suitability scoring for the suitability skill.

Combines a standalone `EquityAssessment` with the user's policy and portfolio
(IPS risk tolerance, single-position concentration limit, allocation drift, and
current holdings) into an advisory `EquityRecommendation`. Like the reviewer,
this deterministic core is the record; the skill's LLM only narrates it. It is
advisory only — it never drafts or executes a trade.

Decision order (first applicable wins):
  1. Excluded by IPS            -> AVOID
  2. Overvalued                 -> TRIM (if held) / AVOID (if not)
  3. Undervalued + has room     -> ADD (if held) / BUY (if not)
  4. Undervalued + no room      -> HOLD (at concentration limit or sleeve full)
  5. Fairly valued              -> HOLD
  6. Unknown (insufficient data)-> HOLD (low conviction)
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from ..contracts.drift_report import DriftReport, DriftReportEntry
from ..contracts.equity_assessment import EquityAssessment, ValuationVerdict
from ..contracts.equity_recommendation import (
    EquityRecommendation,
    RecommendationDirection,
    SuitabilityFactor,
)
from ..contracts.holdings import HoldingsSnapshot, Position
from ..contracts.ips import InvestmentPolicyStatement, RiskTolerance
from ..contracts.profile import UserProfile
from ..contracts.research_brief import ConfidenceLevel
from ..logger import get_logger

logger = get_logger(__name__)

_DEFAULT_ASSET_CLASS = "Equity"
_STRONG_UPSIDE_PCT = 30.0

_DISCLAIMERS = [
    "Advisory only and not investment advice; you make the final decision.",
    "This does not place a trade — any order still goes through review and your approval.",
]


@dataclass(frozen=True)
class _Downgrade:
    """Small helper to step a ConfidenceLevel down."""

    order = (ConfidenceLevel.LOW, ConfidenceLevel.MEDIUM, ConfidenceLevel.HIGH)

    @classmethod
    def step_down(cls, level: ConfidenceLevel, by: int = 1) -> ConfidenceLevel:
        idx = cls.order.index(level)
        return cls.order[max(0, idx - by)]

    @classmethod
    def cap(cls, level: ConfidenceLevel, ceiling: ConfidenceLevel) -> ConfidenceLevel:
        return level if cls.order.index(level) <= cls.order.index(ceiling) else ceiling


def _find_position(holdings: HoldingsSnapshot, ticker: str) -> Optional[Position]:
    for pos in holdings.positions:
        if pos.ticker.upper() == ticker:
            return pos
    return None


def _portfolio_total(holdings: HoldingsSnapshot) -> float:
    if holdings.total_value_usd:
        return holdings.total_value_usd
    return sum(p.market_value_usd for p in holdings.positions) + (holdings.cash_usd or 0.0)


def _find_band(drift: Optional[DriftReport], asset_class: str) -> Optional[DriftReportEntry]:
    if drift is None:
        return None
    for band in drift.bands:
        if band.asset_class.lower() == asset_class.lower():
            return band
    return None


def recommend(
    assessment: EquityAssessment,
    ips: InvestmentPolicyStatement,
    holdings: HoldingsSnapshot,
    drift: Optional[DriftReport] = None,
    profile: Optional[UserProfile] = None,
) -> EquityRecommendation:
    """Produces an advisory EquityRecommendation from the standalone assessment + user policy."""
    ticker = assessment.ticker.upper()
    verdict = assessment.valuation_verdict
    upside = assessment.dcf.upside_pct if assessment.dcf else None
    risk = ips.risk_tolerance

    factors: list[SuitabilityFactor] = []

    # --- Portfolio context ---------------------------------------------------
    position = _find_position(holdings, ticker)
    held = position is not None
    total = _portfolio_total(holdings)
    current_weight = (position.market_value_usd / total * 100.0) if (held and total > 0) else 0.0
    conc_limit = ips.constraints.concentration_limit_percent
    headroom = conc_limit - current_weight
    at_or_over_limit = current_weight >= conc_limit

    asset_class = position.asset_class if held else _DEFAULT_ASSET_CLASS
    band = _find_band(drift, asset_class)
    over_allocated = bool(band and band.current_percent > band.max_percent)
    under_allocated = bool(band and band.current_percent < band.target_percent)
    sleeve_has_room = (band is None) or (band.current_percent < band.max_percent)

    excluded = ticker in {t.upper() for t in ips.constraints.excluded_tickers}

    # --- Factors (transparent inputs) ---------------------------------------
    factors.append(
        SuitabilityFactor(
            name="valuation",
            detail=f"Standalone valuation verdict is {verdict.value}"
            + (f" ({upside:.0f}% DCF upside)" if upside is not None else ""),
            favorable=(verdict == ValuationVerdict.UNDERVALUED)
            if verdict in (ValuationVerdict.UNDERVALUED, ValuationVerdict.OVERVALUED)
            else None,
        )
    )
    if held:
        factors.append(
            SuitabilityFactor(
                name="concentration",
                detail=f"You already hold {ticker} at {current_weight:.1f}% of the portfolio "
                f"(limit {conc_limit:.0f}%, headroom {headroom:.1f}%).",
                favorable=not at_or_over_limit,
            )
        )
    else:
        factors.append(
            SuitabilityFactor(
                name="concentration",
                detail=f"Not currently held; a new position would sit under the {conc_limit:.0f}% limit.",
                favorable=True,
            )
        )
    if band is not None:
        factors.append(
            SuitabilityFactor(
                name="allocation_room",
                detail=f"{asset_class} is at {band.current_percent:.1f}% vs target {band.target_percent:.1f}% "
                f"(band {band.min_percent:.0f}-{band.max_percent:.0f}%).",
                favorable=under_allocated if not over_allocated else False,
            )
        )
    factors.append(
        SuitabilityFactor(
            name="risk_tolerance",
            detail=f"IPS risk tolerance is {risk.value}; single-name concentration adds idiosyncratic risk.",
            favorable=None if risk == RiskTolerance.MODERATE else (risk == RiskTolerance.AGGRESSIVE),
        )
    )

    # --- Direction decision --------------------------------------------------
    conviction = assessment.confidence
    if excluded:
        direction = RecommendationDirection.AVOID
        conviction = ConfidenceLevel.HIGH
        factors.append(
            SuitabilityFactor(name="exclusion", detail=f"{ticker} is on the IPS excluded list.", favorable=False)
        )
    elif verdict == ValuationVerdict.OVERVALUED:
        direction = RecommendationDirection.TRIM if held else RecommendationDirection.AVOID
    elif verdict == ValuationVerdict.UNDERVALUED:
        if at_or_over_limit or over_allocated:
            direction = RecommendationDirection.HOLD  # attractive, but no room to add safely
            conviction = _Downgrade.step_down(conviction)
        else:
            direction = RecommendationDirection.ADD if held else RecommendationDirection.BUY
            if risk == RiskTolerance.CONSERVATIVE:
                conviction = _Downgrade.cap(conviction, ConfidenceLevel.MEDIUM)
            elif (
                risk == RiskTolerance.AGGRESSIVE
                and upside is not None
                and upside >= _STRONG_UPSIDE_PCT
                and under_allocated
            ):
                conviction = ConfidenceLevel.HIGH
    elif verdict == ValuationVerdict.FAIRLY_VALUED:
        direction = RecommendationDirection.HOLD
    else:  # UNKNOWN
        direction = RecommendationDirection.HOLD
        conviction = ConfidenceLevel.LOW

    # --- Risks ---------------------------------------------------------------
    key_risks = list(assessment.key_risks)
    if direction in (RecommendationDirection.BUY, RecommendationDirection.ADD) and headroom < (conc_limit / 2):
        key_risks.append(
            f"Adding would use much of your remaining concentration headroom ({headroom:.1f}% to the {conc_limit:.0f}% limit)."
        )
    if verdict == ValuationVerdict.UNKNOWN:
        key_risks.append("Valuation could not be computed from available data; treat this as low-confidence.")

    rationale = _rationale(ticker, verdict, upside, held, current_weight, direction, risk)

    return EquityRecommendation(
        ticker=ticker,
        as_of=datetime.now(timezone.utc),
        direction=direction,
        conviction=conviction,
        rationale=rationale,
        valuation_verdict=verdict,
        upside_pct=upside,
        assessment_confidence=assessment.confidence,
        already_held=held,
        current_weight_pct=current_weight,
        concentration_limit_pct=conc_limit,
        headroom_pct=headroom,
        suitability_factors=factors,
        key_risks=key_risks,
        disclaimers=list(_DISCLAIMERS),
    )


def _rationale(
    ticker: str,
    verdict: ValuationVerdict,
    upside: Optional[float],
    held: bool,
    current_weight: float,
    direction: RecommendationDirection,
    risk: RiskTolerance,
) -> str:
    val = f"{ticker} looks {verdict.value}"
    if upside is not None:
        val += f" (~{upside:.0f}% DCF upside)"
    hold_txt = f"you hold {current_weight:.1f}%" if held else "you don't currently hold it"
    return (
        f"{val}; {hold_txt}, and your IPS risk tolerance is {risk.value}. "
        f"On balance the suitability-adjusted lean is to {direction.value}."
    )
