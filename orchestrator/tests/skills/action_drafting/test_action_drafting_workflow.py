from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from orchestrator.contracts import ConfidenceLevel, ResearchBrief
from orchestrator.contracts.audit_log import EventType
from orchestrator.contracts.holdings import HoldingsSnapshot, Position
from orchestrator.contracts.ips import (
    Constraints,
    InvestmentPolicyStatement,
    IPSStatus,
    RiskTolerance,
    TargetAllocation,
)
from orchestrator.skills.action_drafting import action_drafting_skill


@pytest.fixture
def mock_firestore():
    with patch("orchestrator.skills.action_drafting.FirestoreClient") as mock:
        yield mock


@pytest.mark.asyncio
async def test_action_drafting_skill_success_with_research_brief(mock_firestore):
    """Verifies action drafting drafts action and links ResearchBrief metadata (D4, M2)."""
    client_instance = mock_firestore.return_value

    ips = InvestmentPolicyStatement(
        ips_id="ips_123",
        user_id="user_1",
        version=2,
        status=IPSStatus.ACTIVE,
        effective_date="2024-01-01",
        risk_tolerance=RiskTolerance.MODERATE,
        time_horizon_years=10,
        target_allocation=[
            TargetAllocation(asset_class="Equity", target_percent=60, min_percent=50, max_percent=70),
        ],
        constraints=Constraints(concentration_limit_percent=15),
        created_at=datetime.now(timezone.utc),
    )
    client_instance.get_active_ips.return_value = ips

    holdings = HoldingsSnapshot(
        user_id="user_1",
        as_of=datetime.now(timezone.utc),
        positions=[
            Position(ticker="AAPL", quantity=100, asset_class="Equity", market_value_usd=15000),
        ],
        cash_usd=5000.0,
        total_value_usd=20000.0,
    )
    client_instance.get_holdings.return_value = holdings

    brief = ResearchBrief(
        research_run_id="run_brief_1",
        summary="Apple supply chain constraints reported.",
        sources=["https://example.com/aapl"],
        confidence=ConfidenceLevel.LOW,
        as_of=datetime.now(timezone.utc),
    )

    node_input = {
        "user_id": "user_1",
        "ips_id": "ips_123",
        "session_id": "session_abc",
        "drift_report": {"rebalance_recommended": True},
        "research_briefs": [brief],
    }

    ctx = MagicMock()
    result = await action_drafting_skill._func(ctx, node_input)

    assert len(result) == 1
    action = result[0]

    # Check outputs
    assert action["type"] == "trade"
    assert action["ticker"] == "AAPL"
    assert action["side"] == "sell"
    assert action["status"] == "drafted"
    assert "Supporting research confidence was low" in action["rationale"]
    assert action["supporting_research_refs"] == ["run_brief_1"]

    # Check IPS reference
    assert action["ips_version_referenced"]["ips_id"] == "ips_123"
    assert action["ips_version_referenced"]["version"] == 2

    # Check specific audit log events (M2)
    assert client_instance.append_audit_log.call_count >= 2
    invoked_log = client_instance.append_audit_log.call_args_list[0][0][0]
    proposed_log = client_instance.append_audit_log.call_args_list[1][0][0]
    assert invoked_log.event_type == EventType.SKILL_INVOKED
    assert proposed_log.event_type == EventType.ACTION_PROPOSED


@pytest.mark.asyncio
async def test_action_drafting_skill_no_action(mock_firestore):
    client_instance = mock_firestore.return_value

    ips = InvestmentPolicyStatement(
        ips_id="ips_123",
        user_id="user_1",
        version=2,
        status=IPSStatus.ACTIVE,
        effective_date="2024-01-01",
        risk_tolerance=RiskTolerance.MODERATE,
        time_horizon_years=10,
        target_allocation=[
            TargetAllocation(asset_class="Equity", target_percent=60, min_percent=50, max_percent=70),
        ],
        constraints=Constraints(concentration_limit_percent=15),
        created_at=datetime.now(timezone.utc),
    )
    client_instance.get_active_ips.return_value = ips

    holdings = HoldingsSnapshot(
        user_id="user_1",
        as_of=datetime.now(timezone.utc),
        positions=[
            Position(ticker="AAPL", quantity=100, asset_class="Equity", market_value_usd=15000),
        ],
        cash_usd=15000.0,
        total_value_usd=30000.0,
    )
    client_instance.get_holdings.return_value = holdings

    node_input = {"user_id": "user_1", "ips_id": "ips_123", "drift_report": {"rebalance_recommended": False}}

    ctx = MagicMock()
    result = await action_drafting_skill._func(ctx, node_input)

    # Zero proposed actions drafted
    assert len(result) == 0


@pytest.mark.asyncio
async def test_action_drafting_skill_constraint_failure_audit_log(mock_firestore):
    """Verifies constraint violation raises ValueError and logs SKILL_INVOCATION_FAILED."""
    client_instance = mock_firestore.return_value

    ips = InvestmentPolicyStatement(
        ips_id="ips_123",
        user_id="user_1",
        version=1,
        status=IPSStatus.ACTIVE,
        effective_date="2024-01-01",
        risk_tolerance=RiskTolerance.MODERATE,
        time_horizon_years=10,
        target_allocation=[
            TargetAllocation(asset_class="Equity", target_percent=60, min_percent=50, max_percent=70),
        ],
        constraints=Constraints(concentration_limit_percent=15, excluded_tickers=["AAPL"]),
        created_at=datetime.now(timezone.utc),
    )
    client_instance.get_active_ips.return_value = ips

    holdings = HoldingsSnapshot(
        user_id="user_1",
        as_of=datetime.now(timezone.utc),
        positions=[
            Position(ticker="AAPL", quantity=100, asset_class="Equity", market_value_usd=15000),
        ],
        cash_usd=5000.0,
        total_value_usd=20000.0,
    )
    client_instance.get_holdings.return_value = holdings

    node_input = {
        "user_id": "user_1",
        "ips_id": "ips_123",
        "drift_report": {"rebalance_recommended": True},
    }

    ctx = MagicMock()
    with pytest.raises(ValueError, match="excluded_tickers"):
        await action_drafting_skill._func(ctx, node_input)

    assert client_instance.append_audit_log.call_count == 2
    failed_log = client_instance.append_audit_log.call_args_list[1][0][0]
    assert failed_log.event_type == EventType.SKILL_INVOCATION_FAILED


@pytest.mark.asyncio
async def test_action_drafting_skill_audit_log_failure_raises(mock_firestore):
    """Verifies I3: If audit log append fails, action drafting fails closed."""
    client_instance = mock_firestore.return_value
    client_instance.append_audit_log.side_effect = RuntimeError("Firestore unavailable")

    node_input = {"user_id": "user_audit_fail"}
    ctx = MagicMock()

    with pytest.raises(RuntimeError, match="Audit log write failed for skill invocation"):
        await action_drafting_skill._func(ctx, node_input)

