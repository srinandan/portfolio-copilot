"""Deterministic valuation core for the equity-research skill.

Turns a `FundamentalsSnapshot` into an `EquityAssessment` using a transparent,
testable DCF plus quality ratios and trading multiples. Mirrors the reviewer
pattern: this deterministic core produces the numbers of record; the skill's LLM
layer only narrates them. Nothing here is investment advice.

The DCF is a standard two-stage model: an explicit FCF projection discounted at a
WACC proxy, plus a Gordon-growth terminal value; equity value is enterprise value
less net debt, divided by shares. Every step guards against missing data and
returns `None` rather than guessing.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from ..contracts.equity_assessment import (
    DcfResult,
    EquityAssessment,
    QualityMetrics,
    TradingMultiples,
    ValuationVerdict,
)
from ..contracts.fundamentals import FinancialPeriod, FundamentalsSnapshot
from ..contracts.research_brief import ConfidenceLevel
from ..logger import get_logger

logger = get_logger(__name__)

_DISCLAIMERS = [
    "Model-derived estimate for informational purposes only; not investment advice.",
    "A DCF is highly sensitive to its growth and discount-rate assumptions.",
]


@dataclass(frozen=True)
class ValuationAssumptions:
    """Tunable DCF and verdict parameters (sensible defaults for a US large-cap)."""

    discount_rate: float = 0.09
    terminal_growth_rate: float = 0.025
    projection_years: int = 5
    default_fcf_growth: float = 0.04
    fcf_growth_floor: float = 0.0
    fcf_growth_cap: float = 0.12
    undervalued_threshold_pct: float = 15.0
    overvalued_threshold_pct: float = 15.0


DEFAULT_ASSUMPTIONS = ValuationAssumptions()


def _cagr(first: Optional[float], last: Optional[float], years: int) -> Optional[float]:
    """Compound annual growth from `first` to `last` over `years`, or None if undefined."""
    if first is None or last is None or years <= 0 or first <= 0 or last <= 0:
        return None
    return (last / first) ** (1.0 / years) - 1.0


def _annual_periods(snapshot: FundamentalsSnapshot) -> list[FinancialPeriod]:
    from ..contracts.fundamentals import FiscalPeriodType

    return [p for p in snapshot.periods if p.period_type == FiscalPeriodType.ANNUAL]


def _fcf_growth(periods: list[FinancialPeriod], assumptions: ValuationAssumptions) -> float:
    """Derives a clamped FCF growth rate from history, falling back to the default."""
    fcfs = [(p.fiscal_year, p.free_cash_flow_usd) for p in periods if p.free_cash_flow_usd is not None]
    growth = assumptions.default_fcf_growth
    if len(fcfs) >= 2:
        newest_year, newest = fcfs[0]
        oldest_year, oldest = fcfs[-1]
        derived = _cagr(oldest, newest, newest_year - oldest_year)
        if derived is not None:
            growth = derived
    return max(assumptions.fcf_growth_floor, min(assumptions.fcf_growth_cap, growth))


def _dcf(
    snapshot: FundamentalsSnapshot,
    periods: list[FinancialPeriod],
    assumptions: ValuationAssumptions,
) -> Optional[DcfResult]:
    """Two-stage DCF → per-share intrinsic value, or None when inputs are insufficient."""
    if not periods:
        return None
    latest = periods[0]
    base_fcf = latest.free_cash_flow_usd
    if base_fcf is None or base_fcf <= 0:
        return None
    if assumptions.discount_rate <= assumptions.terminal_growth_rate:
        # Terminal value diverges; refuse to produce a misleading number.
        return None

    g = _fcf_growth(periods, assumptions)
    r = assumptions.discount_rate
    tg = assumptions.terminal_growth_rate
    n = assumptions.projection_years

    pv_sum = 0.0
    fcf_t = base_fcf
    for t in range(1, n + 1):
        fcf_t = base_fcf * (1 + g) ** t
        pv_sum += fcf_t / (1 + r) ** t
    terminal_value = fcf_t * (1 + tg) / (r - tg)
    pv_terminal = terminal_value / (1 + r) ** n
    enterprise_value = pv_sum + pv_terminal

    net_debt = None
    if latest.total_debt_usd is not None or latest.cash_and_equivalents_usd is not None:
        net_debt = (latest.total_debt_usd or 0.0) - (latest.cash_and_equivalents_usd or 0.0)
    equity_value = enterprise_value - (net_debt or 0.0)

    shares = snapshot.shares_outstanding or latest.shares_diluted
    intrinsic_per_share = equity_value / shares if shares and shares > 0 else None

    price = snapshot.latest_price_usd
    upside = None
    if intrinsic_per_share is not None and price is not None and price > 0:
        upside = (intrinsic_per_share - price) / price * 100.0

    return DcfResult(
        intrinsic_value_per_share_usd=intrinsic_per_share,
        current_price_usd=price,
        upside_pct=upside,
        enterprise_value_usd=enterprise_value,
        equity_value_usd=equity_value,
        net_debt_usd=net_debt,
        base_fcf_usd=base_fcf,
        fcf_growth_rate=g,
        discount_rate=r,
        terminal_growth_rate=tg,
        projection_years=n,
    )


def _quality(periods: list[FinancialPeriod]) -> Optional[QualityMetrics]:
    if not periods:
        return None
    latest = periods[0]

    def pct(numer: Optional[float], denom: Optional[float]) -> Optional[float]:
        if numer is None or denom is None or denom == 0:
            return None
        return numer / denom * 100.0

    def ratio(numer: Optional[float], denom: Optional[float]) -> Optional[float]:
        if numer is None or denom is None or denom == 0:
            return None
        return numer / denom

    revenue_cagr = None
    revs = [(p.fiscal_year, p.revenue_usd) for p in periods if p.revenue_usd is not None]
    if len(revs) >= 2:
        derived = _cagr(revs[-1][1], revs[0][1], revs[0][0] - revs[-1][0])
        revenue_cagr = derived * 100.0 if derived is not None else None

    return QualityMetrics(
        net_margin_pct=pct(latest.net_income_usd, latest.revenue_usd),
        fcf_margin_pct=pct(latest.free_cash_flow_usd, latest.revenue_usd),
        revenue_cagr_pct=revenue_cagr,
        return_on_equity_pct=pct(latest.net_income_usd, latest.total_equity_usd),
        debt_to_equity=ratio(latest.total_debt_usd, latest.total_equity_usd),
    )


def _multiples(
    snapshot: FundamentalsSnapshot,
    periods: list[FinancialPeriod],
    dcf: Optional[DcfResult],
) -> Optional[TradingMultiples]:
    price = snapshot.latest_price_usd
    if not periods or price is None or price <= 0:
        return None
    latest = periods[0]
    shares = snapshot.shares_outstanding or latest.shares_diluted
    if not shares or shares <= 0:
        return None
    market_cap = price * shares

    def div(numer: Optional[float], denom: Optional[float]) -> Optional[float]:
        if numer is None or denom is None or denom == 0:
            return None
        return numer / denom

    eps = div(latest.net_income_usd, shares)
    ev = market_cap + (dcf.net_debt_usd if dcf and dcf.net_debt_usd is not None else 0.0)
    return TradingMultiples(
        market_cap_usd=market_cap,
        price_to_earnings=div(price, eps),
        price_to_fcf=div(market_cap, latest.free_cash_flow_usd),
        ev_to_operating_income=div(ev, latest.operating_income_usd),
    )


def _verdict(dcf: Optional[DcfResult], assumptions: ValuationAssumptions) -> ValuationVerdict:
    if dcf is None or dcf.upside_pct is None:
        return ValuationVerdict.UNKNOWN
    if dcf.upside_pct >= assumptions.undervalued_threshold_pct:
        return ValuationVerdict.UNDERVALUED
    if dcf.upside_pct <= -assumptions.overvalued_threshold_pct:
        return ValuationVerdict.OVERVALUED
    return ValuationVerdict.FAIRLY_VALUED


def _confidence(dcf: Optional[DcfResult], num_periods: int) -> ConfidenceLevel:
    if dcf is None or dcf.upside_pct is None:
        return ConfidenceLevel.LOW
    return ConfidenceLevel.HIGH if num_periods >= 3 else ConfidenceLevel.MEDIUM


def _drivers_and_risks(
    quality: Optional[QualityMetrics], dcf: Optional[DcfResult]
) -> tuple[list[str], list[str]]:
    drivers: list[str] = []
    risks: list[str] = []
    if quality:
        if quality.fcf_margin_pct is not None:
            drivers.append(f"Free-cash-flow margin of {quality.fcf_margin_pct:.1f}%.")
        if quality.revenue_cagr_pct is not None:
            (drivers if quality.revenue_cagr_pct >= 0 else risks).append(
                f"Revenue CAGR of {quality.revenue_cagr_pct:.1f}% over the reported window."
            )
        if quality.net_margin_pct is not None and quality.net_margin_pct < 0:
            risks.append(f"Unprofitable on a net basis (net margin {quality.net_margin_pct:.1f}%).")
        if quality.debt_to_equity is not None and quality.debt_to_equity > 2.0:
            risks.append(f"Elevated leverage (debt/equity {quality.debt_to_equity:.1f}).")
    if dcf and dcf.upside_pct is not None:
        if dcf.upside_pct >= 0:
            drivers.append(f"DCF implies about {dcf.upside_pct:.0f}% upside to intrinsic value.")
        else:
            risks.append(f"Trades about {abs(dcf.upside_pct):.0f}% above DCF intrinsic value.")
    return drivers, risks


def assess_equity(
    snapshot: FundamentalsSnapshot,
    assumptions: ValuationAssumptions = DEFAULT_ASSUMPTIONS,
) -> EquityAssessment:
    """Builds a standalone `EquityAssessment` from a `FundamentalsSnapshot`."""
    periods = _annual_periods(snapshot)
    dcf = _dcf(snapshot, periods, assumptions)
    quality = _quality(periods)
    multiples = _multiples(snapshot, periods, dcf)
    verdict = _verdict(dcf, assumptions)
    confidence = _confidence(dcf, len(periods))
    drivers, risks = _drivers_and_risks(quality, dcf)

    return EquityAssessment(
        ticker=snapshot.ticker.upper(),
        company_name=snapshot.company_name,
        as_of=datetime.now(timezone.utc),
        data_source=snapshot.source.value,
        dcf=dcf,
        quality=quality,
        multiples=multiples,
        valuation_verdict=verdict,
        confidence=confidence,
        key_drivers=drivers,
        key_risks=risks,
        disclaimers=list(_DISCLAIMERS),
    )
