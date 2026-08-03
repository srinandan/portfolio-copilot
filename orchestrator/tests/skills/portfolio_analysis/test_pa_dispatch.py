from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.contracts.drift_report import DriftReport
from orchestrator.contracts.holdings import HoldingsSnapshot, Position
from orchestrator.contracts.ips import (
    Constraints,
    InvestmentPolicyStatement,
    IPSStatus,
    RebalancingRules,
    RiskTolerance,
    TargetAllocation,
)
from orchestrator.planner import SKILL_PLANS, _execute_skill


@pytest.fixture
def sample_ips():
    return InvestmentPolicyStatement(
        ips_id="ips_1",
        user_id="user_123",
        version=1,
        status=IPSStatus.ACTIVE,
        effective_date=date(2023, 1, 1),
        risk_tolerance=RiskTolerance.MODERATE,
        time_horizon_years=10,
        target_allocation=[
            TargetAllocation(asset_class="Equity", target_percent=60.0, min_percent=50.0, max_percent=70.0),
            TargetAllocation(asset_class="Fixed Income", target_percent=40.0, min_percent=30.0, max_percent=50.0),
        ],
        constraints=Constraints(concentration_limit_percent=100.0, excluded_tickers=[]),
        rebalancing_rules=RebalancingRules(drift_threshold_percent=5.0),
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_holdings():
    return HoldingsSnapshot(
        user_id="user_123",
        as_of=datetime.now(timezone.utc),
        positions=[
            Position(ticker="VTI", quantity=100, asset_class="Equity", market_value_usd=60000.0),
            Position(ticker="BND", quantity=100, asset_class="Fixed Income", market_value_usd=40000.0),
        ],
        cash_usd=0.0,
        total_value_usd=100000.0,
    )


@pytest.mark.asyncio
@patch("orchestrator.state.preloader.FirestoreClient")
@patch("orchestrator.planner.emit_skill_invoked_audit")
@patch("orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock)
async def test_pa_dispatch_happy_path(mock_dispatch, mock_emit_invoked, mock_fs_cls, sample_ips, sample_holdings):
    mock_fs = mock_fs_cls.return_value
    mock_fs.get_active_ips_by_user.return_value = sample_ips
    mock_fs.get_holdings.return_value = sample_holdings

    expected_report = DriftReport(
        entries=[],
        unclassified_value_usd=0.0,
        rebalance_recommended=False,
    )
    mock_dispatch.return_value = expected_report

    context = {}
    ctx = MagicMock()
    plan = SKILL_PLANS["private-portfolio-analysis"]

    payload = await _execute_skill(plan, "private-portfolio-analysis", "user_123", {}, context, ctx)

    assert payload is not None
    assert "entries" in payload
    assert "rebalance_recommended" in payload
    assert "drift_report" in context
    assert context["drift_report"] == expected_report.model_dump()
    mock_emit_invoked.assert_called_once()


@pytest.mark.asyncio
@patch("orchestrator.state.preloader.FirestoreClient")
@patch("orchestrator.planner.emit_skill_invoked_audit")
@patch("orchestrator.planner.emit_skill_failed_audit")
async def test_pa_dispatch_no_ips_declines_gracefully(mock_emit_failed, mock_emit_invoked, mock_fs_cls):
    mock_fs = mock_fs_cls.return_value
    mock_fs.get_active_ips_by_user.return_value = None

    context = {}
    ctx = MagicMock()
    plan = SKILL_PLANS["private-portfolio-analysis"]

    payload = await _execute_skill(plan, "private-portfolio-analysis", "user_123", {}, context, ctx)

    assert payload == {"status": "declined", "message": "No active IPS found for user user_123; complete goals onboarding first."}
    mock_emit_failed.assert_called_once()
    assert "declined" in mock_emit_failed.call_args[1]["error"]
    mock_emit_invoked.assert_not_called()


@pytest.mark.asyncio
@patch("orchestrator.state.preloader.FirestoreClient")
@patch("orchestrator.planner.emit_skill_invoked_audit")
@patch("orchestrator.planner.emit_skill_failed_audit")
@patch("orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock)
async def test_pa_dispatch_ma_failure_raises(mock_dispatch, mock_emit_failed, mock_emit_invoked, mock_fs_cls, sample_ips, sample_holdings):
    mock_fs = mock_fs_cls.return_value
    mock_fs.get_active_ips_by_user.return_value = sample_ips
    mock_fs.get_holdings.return_value = sample_holdings
    mock_dispatch.side_effect = RuntimeError("MA service unavailable")

    context = {}
    ctx = MagicMock()
    plan = SKILL_PLANS["private-portfolio-analysis"]

    with pytest.raises(RuntimeError, match="MA service unavailable"):
        await _execute_skill(plan, "private-portfolio-analysis", "user_123", {}, context, ctx)

    mock_emit_failed.assert_called_once()
    assert "dispatch_failed" in mock_emit_failed.call_args[1]["error"]
    mock_emit_invoked.assert_called_once()
