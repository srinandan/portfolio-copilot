from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from orchestrator.contracts.audit_log import EventType
from orchestrator.contracts.holdings import HoldingsSnapshot, Position
from orchestrator.contracts.ips import (
    Constraints,
    InvestmentPolicyStatement,
    IPSStatus,
    RebalancingRules,
    RiskTolerance,
    TargetAllocation,
)
from orchestrator.skills.portfolio_analysis import portfolio_analysis_skill


@pytest.mark.asyncio
async def test_portfolio_analysis_skill_missing_user_id():
    ctx = MagicMock()
    node_input = {}

    with pytest.raises(ValueError, match="user_id is required"):
        gen = portfolio_analysis_skill.run(ctx=ctx, node_input=node_input)
        async for _ in gen:
            pass


@pytest.mark.asyncio
@patch("orchestrator.skills.portfolio_analysis.FirestoreClient")
async def test_portfolio_analysis_skill_no_ips(mock_firestore_class):
    mock_db = mock_firestore_class.return_value
    mock_db.get_active_ips_by_user.return_value = None

    ctx = MagicMock()
    node_input = {"user_id": "test_user"}

    gen = portfolio_analysis_skill.run(ctx=ctx, node_input=node_input)
    result = None
    async for item in gen:
        result = item.output

    assert result["status"] == "declined"
    assert "No active Investment Policy Statement" in result["message"]

    # Verify audit logs: SKILL_INVOKED on entry and SKILL_INVOCATION_FAILED on decline
    assert mock_db.append_audit_log.call_count == 2
    invoked_call = mock_db.append_audit_log.call_args_list[0][0][0]
    assert invoked_call.event_type == EventType.SKILL_INVOKED
    assert invoked_call.actor.skill_name == "private-portfolio-analysis"
    assert invoked_call.actor.skill_version == "0.1.0"

    failed_call = mock_db.append_audit_log.call_args_list[1][0][0]
    assert failed_call.event_type == EventType.SKILL_INVOCATION_FAILED


@pytest.mark.asyncio
@patch("orchestrator.skills.portfolio_analysis.FirestoreClient")
async def test_portfolio_analysis_skill_no_holdings(mock_firestore_class):
    mock_db = mock_firestore_class.return_value
    mock_db.get_active_ips_by_user.return_value = InvestmentPolicyStatement(
        ips_id="ips_1",
        user_id="test_user",
        version=1,
        status=IPSStatus.ACTIVE,
        effective_date=date(2023, 1, 1),
        risk_tolerance=RiskTolerance.MODERATE,
        time_horizon_years=10,
        target_allocation=[
            TargetAllocation(asset_class="Equity", target_percent=100.0, min_percent=90.0, max_percent=100.0),
        ],
        constraints=Constraints(concentration_limit_percent=15),
        created_at=datetime.now(timezone.utc),
    )
    mock_db.get_holdings.return_value = None

    ctx = MagicMock()
    node_input = {"user_id": "test_user"}

    gen = portfolio_analysis_skill.run(ctx=ctx, node_input=node_input)
    result = None
    async for item in gen:
        result = item.output

    assert result["status"] == "declined"
    assert "No holdings found" in result["message"]

    assert mock_db.append_audit_log.call_count == 2
    assert mock_db.append_audit_log.call_args_list[1][0][0].event_type == EventType.SKILL_INVOCATION_FAILED


@pytest.mark.asyncio
@patch("orchestrator.skills.portfolio_analysis.FirestoreClient")
async def test_portfolio_analysis_skill_end_to_end_integration(mock_firestore_class):
    """Verifies D3: End-to-end data plumbing from real Firestore contracts through calculate_drift."""
    mock_db = mock_firestore_class.return_value
    now = datetime.now(timezone.utc)

    real_ips = InvestmentPolicyStatement(
        ips_id="ips_e2e",
        user_id="user_e2e",
        version=1,
        status=IPSStatus.ACTIVE,
        effective_date=date(2026, 1, 1),
        risk_tolerance=RiskTolerance.MODERATE,
        time_horizon_years=10,
        target_allocation=[
            TargetAllocation(asset_class="Equity", target_percent=60.0, min_percent=50.0, max_percent=70.0),
            TargetAllocation(asset_class="Fixed Income", target_percent=30.0, min_percent=20.0, max_percent=40.0),
            TargetAllocation(asset_class="Cash", target_percent=10.0, min_percent=5.0, max_percent=15.0),
        ],
        constraints=Constraints(concentration_limit_percent=15),
        rebalancing_rules=RebalancingRules(drift_threshold_percent=5.0),
        created_at=now,
    )
    real_holdings = HoldingsSnapshot(
        user_id="user_e2e",
        as_of=now,
        positions=[
            Position(ticker="VTI", quantity=100, asset_class="Equity", market_value_usd=75000),
            Position(ticker="BND", quantity=100, asset_class="Fixed Income", market_value_usd=15000),
        ],
        cash_usd=10000,
        total_value_usd=100000,
    )

    mock_db.get_active_ips_by_user.return_value = real_ips
    mock_db.get_holdings.return_value = real_holdings

    ctx = MagicMock()
    node_input = {"user_id": "user_e2e"}

    gen = portfolio_analysis_skill.run(ctx=ctx, node_input=node_input)
    result = None
    async for item in gen:
        result = item.output

    assert result["status"] == "completed"
    report_dict = result["drift_report"]
    assert report_dict["rebalance_recommended"] is True
    assert report_dict["unclassified_value_usd"] == 0.0

    entry_map = {e["asset_class"]: e for e in report_dict["entries"]}
    assert entry_map["Equity"]["current_percent"] == 75.0
    assert entry_map["Equity"]["in_band"] is False
    assert entry_map["Equity"]["drift_amount_percent"] == 5.0

    # Verify audit log was emitted
    assert mock_db.append_audit_log.call_count >= 1
    log_entry = mock_db.append_audit_log.call_args_list[0][0][0]
    assert log_entry.event_type == EventType.SKILL_INVOKED
    assert log_entry.actor.skill_name == "private-portfolio-analysis"
    assert log_entry.actor.skill_version == "0.1.0"
