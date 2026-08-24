"""Dispatch-path tests for equity-research + suitability SkillPlans (offline).

Mirrors the per-skill dispatch tests: patch FirestoreClient / the fundamentals
provider / the Managed-Agent dispatch, then drive `_execute_skill` and assert the
deterministic authoritative payload and the context threading
(equity_assessment -> suitability -> equity_recommendation).
"""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

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
from orchestrator.planner import SKILL_PLANS, _execute_skill, _extract_ticker
from orchestrator.primitives.equity_research import assess_equity


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


def test_equity_skill_plans_registered():
    assert "private-equity-research" in SKILL_PLANS
    assert "private-suitability" in SKILL_PLANS


def test_extract_ticker():
    assert _extract_ticker("should I buy AAPL now?", {}) == "AAPL"
    assert _extract_ticker("buy $tsla please", {}) == "TSLA"
    assert _extract_ticker("", {"ticker": "nvda"}) == "NVDA"
    assert _extract_ticker("how is my portfolio doing?", {}) is None
    assert _extract_ticker("what's in my IPS?", {}) is None  # finance-acronym stopword


@pytest.mark.asyncio
@patch("orchestrator.state.preloader._default_fundamentals_provider")
@patch("orchestrator.planner.emit_skill_invoked_audit")
@patch("orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock)
async def test_equity_research_dispatch_threads_assessment(mock_dispatch, mock_emit, mock_provider_factory):
    mock_provider_factory.return_value = MockFundamentalsProvider()
    mock_dispatch.return_value = {"summary": "AAPL trades below our DCF estimate."}

    context = {}
    ctx = MagicMock()
    plan = SKILL_PLANS["private-equity-research"]

    payload = await _execute_skill(plan, "private-equity-research", "u1", {"ticker": "AAPL"}, context, ctx)

    assert payload["ticker"] == "AAPL"
    assert payload["narrative_summary"] == "AAPL trades below our DCF estimate."
    # Assessment is threaded forward for suitability.
    assert context["equity_assessment"]["ticker"] == "AAPL"
    mock_emit.assert_called_once()


@pytest.mark.asyncio
@patch("orchestrator.planner.emit_skill_invoked_audit")
@patch("orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock)
async def test_equity_research_skips_without_ticker(mock_dispatch, mock_emit):
    context = {}
    ctx = MagicMock()
    plan = SKILL_PLANS["private-equity-research"]

    payload = await _execute_skill(plan, "private-equity-research", "u1", {"message": "how is my portfolio?"}, context, ctx)

    assert payload is None  # skipped: no ticker
    mock_dispatch.assert_not_called()
    assert "equity_assessment" not in context


@pytest.mark.asyncio
@patch("orchestrator.state.preloader.FirestoreClient")
@patch("orchestrator.planner.emit_skill_invoked_audit")
@patch("orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock)
async def test_suitability_dispatch_produces_recommendation(mock_dispatch, mock_emit, mock_fs_cls):
    mock_fs = mock_fs_cls.return_value
    mock_fs.get_active_ips_by_user.return_value = _ips()
    mock_fs.get_holdings.return_value = _holdings()
    mock_dispatch.return_value = {"rationale": "narrative"}

    context = {"equity_assessment": _assessment_dict()}
    ctx = MagicMock()
    plan = SKILL_PLANS["private-suitability"]

    payload = await _execute_skill(plan, "private-suitability", "u1", {}, context, ctx)

    assert payload["ticker"] == "AAPL"
    assert payload["direction"] in {"buy", "add", "hold", "trim", "avoid"}
    assert context["equity_recommendation"]["ticker"] == "AAPL"


@pytest.mark.asyncio
@patch("orchestrator.planner.emit_skill_invoked_audit")
@patch("orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock)
async def test_suitability_skips_without_assessment(mock_dispatch, mock_emit):
    context = {}  # no equity_assessment threaded
    ctx = MagicMock()
    plan = SKILL_PLANS["private-suitability"]

    payload = await _execute_skill(plan, "private-suitability", "u1", {}, context, ctx)

    assert payload is None
    mock_dispatch.assert_not_called()
