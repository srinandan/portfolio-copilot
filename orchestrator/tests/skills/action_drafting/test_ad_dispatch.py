from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.contracts.holdings import HoldingsSnapshot, Position
from orchestrator.contracts.ips import (
    Constraints,
    InvestmentPolicyStatement,
    IPSStatus,
    RebalancingRules,
    RelatedIPSVersion,
    RiskTolerance,
    TargetAllocation,
)
from orchestrator.contracts.proposed_action import (
    ActionStatus,
    ActionType,
    OrderType,
    ProposedAction,
    Side,
    SkillVersionRef,
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
            Position(ticker="VTI", quantity=1000, asset_class="Equity", market_value_usd=80000.0),
        ],
        cash_usd=20000.0,
        total_value_usd=100000.0,
    )


@pytest.fixture
def sample_proposed_action():
    return ProposedAction(
        action_id="act_1",
        session_id="sess_1",
        type=ActionType.TRADE,
        ticker="VTI",
        side=Side.BUY,
        quantity=10.0,
        order_type=OrderType.MARKET,
        estimated_price_usd=100.0,
        estimated_value_usd=1000.0,
        rationale="Trade rationale",
        supporting_research_refs=[],
        ips_version_referenced=RelatedIPSVersion(ips_id="ips_1", version=1),
        proposed_by_skill_version=SkillVersionRef(skill_name="private-action-drafting", skill_version="0.1.0"),
        status=ActionStatus.DRAFTED,
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
@patch("orchestrator.state.preloader.FirestoreClient")
@patch("orchestrator.planner.emit_skill_invoked_audit")
@patch("orchestrator.planner.write_proposed_action")
@patch("orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock)
async def test_ad_dispatch_writes_proposed_action(mock_dispatch, mock_write, mock_emit_invoked, mock_fs_cls, sample_ips, sample_holdings, sample_proposed_action):
    mock_fs = mock_fs_cls.return_value
    mock_fs.get_active_ips_by_user.return_value = sample_ips
    mock_fs.get_holdings.return_value = sample_holdings
    mock_dispatch.return_value = sample_proposed_action

    context = {}
    ctx = MagicMock()
    plan = SKILL_PLANS["private-action-drafting"]

    payload = await _execute_skill(plan, "private-action-drafting", "user_123", {}, context, ctx)

    mock_write.assert_called_once_with(user_id="user_123", action=sample_proposed_action)
    assert payload == sample_proposed_action.model_dump()
    assert context["action_drafting_result"] == sample_proposed_action.model_dump()
    mock_emit_invoked.assert_called_once()


@pytest.mark.asyncio
@patch("orchestrator.state.preloader.FirestoreClient")
@patch("orchestrator.planner.emit_skill_invoked_audit")
@patch("orchestrator.state.preloader.calculate_draft_action")
@patch("orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock)
async def test_ad_dispatch_consumes_drift_report_from_context(mock_dispatch, mock_calc, mock_emit_invoked, mock_fs_cls, sample_ips, sample_holdings):
    mock_fs = mock_fs_cls.return_value
    mock_fs.get_active_ips_by_user.return_value = sample_ips
    mock_fs.get_holdings.return_value = sample_holdings
    mock_calc.return_value = None
    mock_dispatch.return_value = {}

    drift_report = {"rebalance_recommended": True, "entries": []}
    context = {"drift_report": drift_report}
    ctx = MagicMock()
    plan = SKILL_PLANS["private-action-drafting"]

    await _execute_skill(plan, "private-action-drafting", "user_123", {}, context, ctx)

    assert mock_calc.called
    assert mock_calc.call_args[0][0] == drift_report
    assert mock_dispatch.call_args[1]["node_input"]["drift_report"] == drift_report
    mock_emit_invoked.assert_called_once()


@pytest.mark.asyncio
@patch("orchestrator.state.preloader.FirestoreClient")
@patch("orchestrator.planner.write_proposed_action")
@patch("orchestrator.planner.emit_skill_failed_audit")
async def test_ad_dispatch_constraint_violation_emits_failed_audit(mock_emit_failed, mock_write, mock_fs_cls, sample_ips, sample_holdings):
    sample_ips.constraints.excluded_tickers = ["TSLA"]
    mock_fs = mock_fs_cls.return_value
    mock_fs.get_active_ips_by_user.return_value = sample_ips
    mock_fs.get_holdings.return_value = sample_holdings

    context = {}
    ctx = MagicMock()
    plan = SKILL_PLANS["private-action-drafting"]

    with pytest.raises(ValueError, match="excluded_tickers"):
        await _execute_skill(
            plan,
            "private-action-drafting",
            "user_123",
            {"requested_trade": {"ticker": "TSLA", "side": "buy", "quantity": 10}},
            context,
            ctx,
        )

    mock_emit_failed.assert_called_once()
    assert "preload_failed" in mock_emit_failed.call_args[1]["error"]
    mock_write.assert_not_called()


@pytest.mark.asyncio
@patch("orchestrator.state.preloader.FirestoreClient")
@patch("orchestrator.planner.emit_skill_invoked_audit")
@patch("orchestrator.planner.emit_skill_failed_audit")
async def test_ad_dispatch_no_ips_declines(mock_emit_failed, mock_emit_invoked, mock_fs_cls):
    mock_fs = mock_fs_cls.return_value
    mock_fs.get_active_ips_by_user.return_value = None

    context = {}
    ctx = MagicMock()
    plan = SKILL_PLANS["private-action-drafting"]

    payload = await _execute_skill(plan, "private-action-drafting", "user_123", {}, context, ctx)

    assert payload == {"status": "declined", "message": "No active IPS found for user user_123."}
    mock_emit_failed.assert_called_once()
    assert "declined" in mock_emit_failed.call_args[1]["error"]
    mock_emit_invoked.assert_not_called()
