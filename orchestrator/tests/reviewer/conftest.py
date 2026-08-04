"""Fixtures for Reviewer unit tests and adversarial checks."""

from datetime import datetime, timezone

import pytest

from orchestrator.contracts.holdings import HoldingsSnapshot, Position
from orchestrator.contracts.ips import (
    Constraints,
    InvestmentPolicyStatement,
    IPSStatus,
    RiskTolerance,
    TargetAllocation,
)
from orchestrator.contracts.proposed_action import (
    ActionStatus,
    ActionType,
    OrderType,
    ProposedAction,
    RelatedIPSVersion,
    Side,
    SkillVersionRef,
)
from orchestrator.reviewer.rules import ReviewInput


@pytest.fixture
def happy_ips() -> InvestmentPolicyStatement:
    return InvestmentPolicyStatement(
        ips_id="ips_happy",
        user_id="user_123",
        version=1,
        status=IPSStatus.ACTIVE,
        effective_date="2026-01-01",
        risk_tolerance=RiskTolerance.MODERATE,
        time_horizon_years=10,
        target_allocation=[
            TargetAllocation(
                asset_class="Equity", target_percent=60, min_percent=50, max_percent=70
            ),
            TargetAllocation(
                asset_class="Bonds", target_percent=40, min_percent=30, max_percent=50
            ),
        ],
        constraints=Constraints(
            concentration_limit_percent=15,
            excluded_tickers=["TSLA"],
            excluded_sectors=["Energy"],
        ),
        approval_required_above_usd=25000.0,
        approval_required_above_percent=20.0,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def happy_holdings() -> HoldingsSnapshot:
    return HoldingsSnapshot(
        user_id="user_123",
        as_of=datetime.now(timezone.utc),
        positions=[
            Position(
                ticker="AAPL",
                quantity=50,
                asset_class="Equity",
                market_value_usd=10000.0,
            ),
            Position(
                ticker="BND",
                quantity=100,
                asset_class="Bonds",
                market_value_usd=10000.0,
            ),
        ],
        cash_usd=80000.0,
        total_value_usd=100000.0,
    )


@pytest.fixture
def happy_action() -> ProposedAction:
    return ProposedAction(
        action_id="act_happy",
        session_id="sess_1",
        type=ActionType.TRADE,
        ticker="AAPL",
        side=Side.BUY,
        quantity=25.0,
        order_type=OrderType.MARKET,
        estimated_price_usd=200.0,
        estimated_value_usd=5000.0,
        rationale="Small buy within concentration limit and target bands.",
        supporting_research_refs=[],
        ips_version_referenced=RelatedIPSVersion(ips_id="ips_happy", version=1),
        proposed_by_skill_version=SkillVersionRef(
            skill_name="private-action-drafting", skill_version="0.1.0"
        ),
        status=ActionStatus.DRAFTED,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def happy_review_input(happy_action, happy_ips, happy_holdings) -> ReviewInput:
    return ReviewInput(action=happy_action, ips=happy_ips, holdings=happy_holdings)
