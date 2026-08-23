"""Unit tests for the deterministic suitability recommendation primitive."""

from datetime import date, datetime, timezone

from orchestrator.contracts.drift_report import DriftReport, DriftReportEntry
from orchestrator.contracts.equity_assessment import DcfResult, EquityAssessment, ValuationVerdict
from orchestrator.contracts.equity_recommendation import RecommendationDirection
from orchestrator.contracts.holdings import HoldingsSnapshot, Position
from orchestrator.contracts.ips import (
    Constraints,
    InvestmentPolicyStatement,
    IPSStatus,
    RiskTolerance,
    TargetAllocation,
)
from orchestrator.contracts.research_brief import ConfidenceLevel
from orchestrator.primitives.suitability import recommend


def _assessment(verdict, upside=None, confidence=ConfidenceLevel.HIGH, ticker="AAPL", risks=None):
    dcf = None
    if upside is not None:
        dcf = DcfResult(
            upside_pct=upside,
            fcf_growth_rate=0.04,
            discount_rate=0.09,
            terminal_growth_rate=0.025,
            projection_years=5,
        )
    return EquityAssessment(
        ticker=ticker,
        as_of=datetime.now(timezone.utc),
        data_source="mock",
        dcf=dcf,
        valuation_verdict=verdict,
        confidence=confidence,
        key_risks=risks or [],
    )


def _ips(risk=RiskTolerance.MODERATE, concentration=15.0, excluded=None):
    return InvestmentPolicyStatement(
        ips_id="ips_1",
        user_id="u1",
        version=1,
        status=IPSStatus.ACTIVE,
        effective_date=date(2024, 1, 1),
        risk_tolerance=risk,
        time_horizon_years=10,
        target_allocation=[TargetAllocation(asset_class="Equity", target_percent=60, min_percent=50, max_percent=70)],
        constraints=Constraints(concentration_limit_percent=concentration, excluded_tickers=excluded or []),
        created_at=datetime.now(timezone.utc),
    )


def _holdings(aapl_value=None, total=100000.0):
    positions = []
    if aapl_value is not None:
        positions.append(Position(ticker="AAPL", quantity=100, asset_class="Equity", market_value_usd=aapl_value))
    return HoldingsSnapshot(user_id="u1", as_of=datetime.now(timezone.utc), positions=positions, total_value_usd=total)


def _drift(current_equity=50.0):
    return DriftReport(
        user_id="u1",
        bands=[
            DriftReportEntry(
                asset_class="Equity",
                current_percent=current_equity,
                target_percent=60,
                min_percent=50,
                max_percent=70,
                in_band=(50 <= current_equity <= 70),
                drift_amount_percent=0.0,
            )
        ],
    )


def test_undervalued_not_held_with_room_is_buy():
    rec = recommend(_assessment(ValuationVerdict.UNDERVALUED, upside=40), _ips(), _holdings(), _drift(current_equity=50))
    assert rec.direction == RecommendationDirection.BUY
    assert rec.already_held is False
    assert rec.upside_pct == 40


def test_undervalued_held_below_limit_is_add():
    rec = recommend(
        _assessment(ValuationVerdict.UNDERVALUED, upside=25),
        _ips(),
        _holdings(aapl_value=5000.0),  # 5% weight, limit 15
        _drift(current_equity=55),
    )
    assert rec.direction == RecommendationDirection.ADD
    assert rec.already_held is True
    assert rec.current_weight_pct == 5.0


def test_undervalued_at_concentration_limit_is_hold():
    rec = recommend(
        _assessment(ValuationVerdict.UNDERVALUED, upside=25),
        _ips(concentration=15.0),
        _holdings(aapl_value=16000.0),  # 16% weight > 15% limit
        _drift(current_equity=60),
    )
    assert rec.direction == RecommendationDirection.HOLD


def test_undervalued_but_sleeve_over_allocated_is_hold():
    rec = recommend(
        _assessment(ValuationVerdict.UNDERVALUED, upside=30),
        _ips(),
        _holdings(),  # not held
        _drift(current_equity=75),  # Equity above max 70 -> no sleeve room
    )
    assert rec.direction == RecommendationDirection.HOLD


def test_overvalued_held_is_trim():
    rec = recommend(
        _assessment(ValuationVerdict.OVERVALUED, upside=-30),
        _ips(),
        _holdings(aapl_value=8000.0),
        _drift(),
    )
    assert rec.direction == RecommendationDirection.TRIM


def test_overvalued_not_held_is_avoid():
    rec = recommend(_assessment(ValuationVerdict.OVERVALUED, upside=-30), _ips(), _holdings(), _drift())
    assert rec.direction == RecommendationDirection.AVOID


def test_excluded_ticker_is_avoid_high_conviction():
    rec = recommend(
        _assessment(ValuationVerdict.UNDERVALUED, upside=50),  # attractive, but excluded
        _ips(excluded=["AAPL"]),
        _holdings(),
        _drift(),
    )
    assert rec.direction == RecommendationDirection.AVOID
    assert rec.conviction == ConfidenceLevel.HIGH


def test_fairly_valued_is_hold():
    rec = recommend(_assessment(ValuationVerdict.FAIRLY_VALUED, upside=3), _ips(), _holdings(), _drift())
    assert rec.direction == RecommendationDirection.HOLD


def test_unknown_verdict_is_low_conviction_hold():
    rec = recommend(_assessment(ValuationVerdict.UNKNOWN, upside=None, confidence=ConfidenceLevel.LOW), _ips(), _holdings(), _drift())
    assert rec.direction == RecommendationDirection.HOLD
    assert rec.conviction == ConfidenceLevel.LOW


def test_conservative_risk_caps_conviction_on_buy():
    rec = recommend(
        _assessment(ValuationVerdict.UNDERVALUED, upside=40, confidence=ConfidenceLevel.HIGH),
        _ips(risk=RiskTolerance.CONSERVATIVE),
        _holdings(),
        _drift(current_equity=50),
    )
    assert rec.direction == RecommendationDirection.BUY
    assert rec.conviction == ConfidenceLevel.MEDIUM  # capped down from HIGH for a conservative investor


def test_recommendation_always_has_disclaimers_and_factors():
    rec = recommend(_assessment(ValuationVerdict.UNDERVALUED, upside=20), _ips(), _holdings(), _drift())
    assert rec.disclaimers
    assert any(f.name == "valuation" for f in rec.suitability_factors)
    assert any(f.name == "risk_tolerance" for f in rec.suitability_factors)


def test_works_without_drift_report():
    rec = recommend(_assessment(ValuationVerdict.UNDERVALUED, upside=25), _ips(), _holdings(), drift=None)
    # No drift => sleeve assumed to have room => BUY.
    assert rec.direction == RecommendationDirection.BUY
