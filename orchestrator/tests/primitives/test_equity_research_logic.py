"""Unit tests for the deterministic equity-research valuation primitive."""

from datetime import datetime, timezone

import pytest

from orchestrator.contracts.equity_assessment import ValuationVerdict
from orchestrator.contracts.fundamentals import (
    FinancialPeriod,
    FiscalPeriodType,
    FundamentalsSnapshot,
    FundamentalsSource,
)
from orchestrator.contracts.research_brief import ConfidenceLevel
from orchestrator.executors.fundamentals import MockFundamentalsProvider
from orchestrator.primitives.equity_research import assess_equity


def _period(fy, **kwargs):
    return FinancialPeriod(fiscal_year=fy, period_type=FiscalPeriodType.ANNUAL, **kwargs)


def _snapshot(periods, *, price=None, shares=None):
    return FundamentalsSnapshot(
        ticker="TEST",
        company_name="Test Co",
        periods=periods,
        latest_price_usd=price,
        shares_outstanding=shares,
        source=FundamentalsSource.MOCK,
        as_of=datetime.now(timezone.utc),
    )


def test_dcf_intrinsic_value_matches_hand_calc():
    # Single FCF point -> default 4% growth; r=9%, tg=2.5%, n=5, no debt, 100 shares.
    snap = _snapshot([_period(2024, free_cash_flow_usd=100.0, total_debt_usd=0.0, cash_and_equivalents_usd=0.0)],
                     price=10.0, shares=100.0)
    a = assess_equity(snap)

    assert a.dcf is not None
    assert a.dcf.base_fcf_usd == 100.0
    assert a.dcf.fcf_growth_rate == pytest.approx(0.04)
    assert a.dcf.discount_rate == 0.09
    # Hand-computed two-stage DCF ~= $16.82/share.
    assert a.dcf.intrinsic_value_per_share_usd == pytest.approx(16.82, rel=0.02)
    assert a.dcf.upside_pct == pytest.approx((16.82 - 10.0) / 10.0 * 100, rel=0.05)
    assert a.valuation_verdict == ValuationVerdict.UNDERVALUED


def test_overvalued_when_price_far_above_intrinsic():
    snap = _snapshot([_period(2024, free_cash_flow_usd=100.0, total_debt_usd=0.0, cash_and_equivalents_usd=0.0)],
                     price=100.0, shares=100.0)
    a = assess_equity(snap)
    assert a.valuation_verdict == ValuationVerdict.OVERVALUED
    assert a.dcf.upside_pct < 0


def test_fcf_growth_derived_from_history_and_clamped():
    # Rising FCF (100 -> 121 over 2y ~ 10% CAGR) is used and within the 12% cap.
    periods = [
        _period(2024, free_cash_flow_usd=121.0, revenue_usd=1000.0),
        _period(2023, free_cash_flow_usd=110.0, revenue_usd=950.0),
        _period(2022, free_cash_flow_usd=100.0, revenue_usd=900.0),
    ]
    a = assess_equity(_snapshot(periods, price=50.0, shares=100.0))
    assert a.dcf.fcf_growth_rate == pytest.approx(0.10, rel=0.02)
    assert a.confidence == ConfidenceLevel.HIGH  # >= 3 annual periods + price


def test_quality_metrics_computed():
    periods = [
        _period(
            2024,
            revenue_usd=1000.0,
            net_income_usd=200.0,
            free_cash_flow_usd=150.0,
            total_equity_usd=500.0,
            total_debt_usd=1200.0,
        ),
        _period(2022, revenue_usd=810.0),
    ]
    a = assess_equity(_snapshot(periods, price=20.0, shares=100.0))
    q = a.quality
    assert q.net_margin_pct == pytest.approx(20.0)
    assert q.fcf_margin_pct == pytest.approx(15.0)
    assert q.return_on_equity_pct == pytest.approx(40.0)
    assert q.debt_to_equity == pytest.approx(2.4)
    # 810 -> 1000 over 2 years ~ 11.1% CAGR
    assert q.revenue_cagr_pct == pytest.approx(11.1, rel=0.05)
    # High leverage should surface as a risk bullet.
    assert any("leverage" in r.lower() for r in a.key_risks)


def test_no_periods_is_unknown_not_error():
    a = assess_equity(_snapshot([], price=10.0, shares=100.0))
    assert a.dcf is None
    assert a.quality is None
    assert a.valuation_verdict == ValuationVerdict.UNKNOWN
    assert a.confidence == ConfidenceLevel.LOW
    assert a.disclaimers  # always present


def test_missing_price_yields_unknown_verdict():
    snap = _snapshot([_period(2024, free_cash_flow_usd=100.0)], price=None, shares=100.0)
    a = assess_equity(snap)
    assert a.dcf is not None
    assert a.dcf.intrinsic_value_per_share_usd is not None
    assert a.dcf.upside_pct is None  # no price to compare
    assert a.valuation_verdict == ValuationVerdict.UNKNOWN


def test_negative_or_missing_fcf_skips_dcf():
    a = assess_equity(_snapshot([_period(2024, revenue_usd=1000.0, net_income_usd=-50.0)], price=10.0, shares=100.0))
    assert a.dcf is None
    assert a.valuation_verdict == ValuationVerdict.UNKNOWN
    # Quality still computed where possible; negative net margin flagged.
    assert a.quality is not None
    assert any("unprofitable" in r.lower() for r in a.key_risks)


def test_runs_on_mock_provider_snapshot():
    snap = MockFundamentalsProvider().get_fundamentals("AAPL")
    a = assess_equity(snap)
    assert a.ticker == "AAPL"
    assert a.dcf is not None
    assert a.multiples is not None
    assert a.multiples.market_cap_usd == pytest.approx(225.0 * 15_115_823_000.0)
