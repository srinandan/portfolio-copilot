from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

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
async def test_action_drafting_skill_success(mock_firestore):
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

    node_input = {
        "user_id": "user_1",
        "ips_id": "ips_123",
        "session_id": "session_abc",
        "drift_report": {"rebalance_recommended": True},
        "research_briefs": {"confidence": "low", "research_run_ids": ["run_1", "run_2"]},
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
    assert "low" in action["rationale"]
    assert action["supporting_research_refs"] == ["run_1", "run_2"]

    # Check IPS reference
    assert action["ips_version_referenced"]["ips_id"] == "ips_123"
    assert action["ips_version_referenced"]["version"] == 2

    # Check audit log calls
    assert client_instance.append_audit_log.call_count == 2


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
