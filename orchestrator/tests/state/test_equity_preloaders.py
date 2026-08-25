"""Unit tests for the equity-research + suitability state preloaders (offline)."""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

from orchestrator.contracts.holdings import HoldingsSnapshot, Position
from orchestrator.contracts.ips import (
    Constraints,
    InvestmentPolicyStatement,
    IPSStatus,
    RiskTolerance,
    TargetAllocation,
)
from orchestrator.executors.fundamentals import MockFundamentalsProvider
from orchestrator.primitives.equity_research import assess_equity
from orchestrator.state.preloader import (
    PreloadDeclinedError,
    preload_for_equity_research,
    preload_for_suitability,
)


def _ips():
    return InvestmentPolicyStatement(
        ips_id="ips_1",
        user_id="u1",
        version=1,
        status=IPSStatus.ACTIVE,
        effective_date=date(2024, 1, 1),
        risk_tolerance=RiskTolerance.MODERATE,
        time_horizon_years=10,
        target_allocation=[
            TargetAllocation(asset_class="Equity", target_percent=60, min_percent=50, max_percent=70),
            TargetAllocation(asset_class="Bonds", target_percent=40, min_percent=30, max_percent=50),
        ],
        constraints=Constraints(concentration_limit_percent=15),
        created_at=datetime.now(timezone.utc),
    )


def _holdings():
    return HoldingsSnapshot(
        user_id="u1",
        as_of=datetime.now(timezone.utc),
        positions=[Position(ticker="VTI", quantity=100, asset_class="Equity", market_value_usd=60000.0)],
        total_value_usd=100000.0,
    )


def _assessment_dict():
    return assess_equity(MockFundamentalsProvider().get_fundamentals("AAPL")).model_dump(mode="json")


# --- equity-research preloader --------------------------------------------- #


def test_preload_equity_research_with_mock_provider():
    out = preload_for_equity_research("u1", "aapl", provider=MockFundamentalsProvider())
    assert out["ticker"] == "AAPL"
    assert out["assessment"]["ticker"] == "AAPL"
    assert out["assessment"]["dcf"] is not None
    assert out["fundamentals"]["source"] == "mock"


def test_preload_equity_research_no_ticker_declines():
    with pytest.raises(PreloadDeclinedError):
        preload_for_equity_research("u1", "")


def test_preload_equity_research_provider_error_declines():
    class Boom:
        def get_fundamentals(self, ticker):
            raise RuntimeError("unknown symbol")

    with pytest.raises(PreloadDeclinedError, match="Could not retrieve fundamentals"):
        preload_for_equity_research("u1", "ZZZZ", provider=Boom())


def test_preload_equity_research_fills_missing_price_from_quote():
    # A provider whose snapshot has no price; quote_fn supplies one.
    base = MockFundamentalsProvider().get_fundamentals("AAPL").model_copy(update={"latest_price_usd": None})

    class NoPriceProvider:
        def get_fundamentals(self, ticker):
            return base

    out = preload_for_equity_research("u1", "AAPL", provider=NoPriceProvider(), quote_fn=lambda s: 199.0)
    assert out["fundamentals"]["latest_price_usd"] == 199.0


# --- suitability preloader -------------------------------------------------- #


def test_preload_suitability_produces_recommendation():
    fs = MagicMock()
    fs.get_active_ips_by_user.return_value = _ips()
    fs.get_holdings.return_value = _holdings()

    out = preload_for_suitability("u1", _assessment_dict(), drift_report=None, firestore_client=fs)
    assert out["ticker"] == "AAPL"
    assert out["recommendation"]["direction"] in {"buy", "add", "hold", "trim", "avoid"}
    assert out["recommendation"]["disclaimers"]


def test_preload_suitability_no_ips_declines():
    fs = MagicMock()
    fs.get_active_ips_by_user.return_value = None
    with pytest.raises(PreloadDeclinedError, match="No active IPS"):
        preload_for_suitability("u1", _assessment_dict(), firestore_client=fs)


def test_preload_suitability_no_assessment_declines():
    with pytest.raises(PreloadDeclinedError, match="No equity assessment"):
        preload_for_suitability("u1", None, firestore_client=MagicMock())
