from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

from orchestrator.contracts.holdings import HoldingsSnapshot, Position
from orchestrator.contracts.ips import (
    Constraints,
    InvestmentPolicyStatement,
    IPSStatus,
    RebalancingRules,
    RiskTolerance,
    TargetAllocation,
)
from orchestrator.state.preloader import (
    PreloadDeclinedError,
    preload_for_action_drafting,
    preload_for_portfolio_analysis,
    preload_for_research,
    preload_for_reviewer,
)
from orchestrator.state.spending import preload_spending_facts


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
            TargetAllocation(asset_class="Fixed Income", target_percent=30.0, min_percent=20.0, max_percent=40.0),
            TargetAllocation(asset_class="Cash", target_percent=10.0, min_percent=5.0, max_percent=15.0),
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
            Position(ticker="BND", quantity=500, asset_class="Fixed Income", market_value_usd=15000.0),
        ],
        cash_usd=5000.0,
        total_value_usd=100000.0,
    )


def test_preload_portfolio_analysis_success(sample_ips, sample_holdings):
    mock_fs = MagicMock()
    mock_fs.get_active_ips_by_user.return_value = sample_ips
    mock_fs.get_holdings.return_value = sample_holdings

    result = preload_for_portfolio_analysis("user_123", firestore_client=mock_fs)

    assert result["user_id"] == "user_123"
    assert result["ips"]["ips_id"] == "ips_1"
    assert result["holdings"]["user_id"] == "user_123"
    assert "drift_report" in result
    assert isinstance(result["drift_report"], dict)
    assert "bands" in result["drift_report"] or "entries" in result["drift_report"]
    assert "rebalance_recommended" in result["drift_report"]
    assert result["drift_report"]["rebalance_recommended"] is True
    assert result["drift_report"]["unclassified_value_usd"] == 0.0


def test_preload_portfolio_analysis_no_ips_raises_declined():
    mock_fs = MagicMock()
    mock_fs.get_active_ips_by_user.return_value = None

    with pytest.raises(PreloadDeclinedError, match="goals onboarding"):
        preload_for_portfolio_analysis("user_123", firestore_client=mock_fs)


def test_preload_portfolio_analysis_no_holdings_raises_declined(sample_ips):
    mock_fs = MagicMock()
    mock_fs.get_active_ips_by_user.return_value = sample_ips
    mock_fs.get_holdings.return_value = None

    with pytest.raises(PreloadDeclinedError, match="No holdings found"):
        preload_for_portfolio_analysis("user_123", firestore_client=mock_fs)


def test_preload_action_drafting_with_drift_report_pre_computes_trade(sample_ips, sample_holdings):
    mock_fs = MagicMock()
    mock_fs.get_active_ips_by_user.return_value = sample_ips
    mock_fs.get_holdings.return_value = sample_holdings

    drift_report = {
        "rebalance_recommended": True,
        "entries": [
            {
                "asset_class": "Equity",
                "current_percent": 80.0,
                "target_percent": 60.0,
                "min_percent": 50.0,
                "max_percent": 70.0,
                "in_band": False,
                "drift_amount_percent": 10.0,
            }
        ],
        "unclassified_value_usd": 0.0,
    }

    result = preload_for_action_drafting(
        user_id="user_123",
        drift_report=drift_report,
        firestore_client=mock_fs,
    )

    assert result["user_id"] == "user_123"
    assert result["drift_report"] == drift_report
    assert "precomputed_trade" in result
    if result["precomputed_trade"] is not None:
        assert isinstance(result["precomputed_trade"], dict)
        assert "ticker" in result["precomputed_trade"]


def test_preload_action_drafting_with_requested_trade(sample_ips, sample_holdings):
    mock_fs = MagicMock()
    mock_fs.get_active_ips_by_user.return_value = sample_ips
    mock_fs.get_holdings.return_value = sample_holdings

    requested_trade = {"ticker": "VTI", "side": "buy", "quantity": 10}
    result = preload_for_action_drafting(
        user_id="user_123",
        requested_trade=requested_trade,
        firestore_client=mock_fs,
    )

    assert result["requested_trade"] == requested_trade
    assert result["precomputed_trade"] is not None
    assert result["precomputed_trade"]["ticker"] == "VTI"
    assert result["precomputed_trade"]["side"] == "buy"
    assert result["precomputed_trade"]["quantity"] == 10


def test_preload_action_drafting_constraint_violation_propagates(sample_holdings):
    mock_fs = MagicMock()
    restricted_ips = InvestmentPolicyStatement(
        ips_id="ips_restricted",
        user_id="user_123",
        version=1,
        status=IPSStatus.ACTIVE,
        effective_date=date(2023, 1, 1),
        risk_tolerance=RiskTolerance.MODERATE,
        time_horizon_years=10,
        target_allocation=[
            TargetAllocation(asset_class="Equity", target_percent=60.0, min_percent=50.0, max_percent=70.0),
        ],
        constraints=Constraints(concentration_limit_percent=100.0, excluded_tickers=["TSLA"]),
        rebalancing_rules=RebalancingRules(drift_threshold_percent=5.0),
        created_at=datetime.now(timezone.utc),
    )
    mock_fs.get_active_ips_by_user.return_value = restricted_ips
    mock_fs.get_holdings.return_value = sample_holdings

    requested_trade = {"ticker": "TSLA", "side": "buy", "quantity": 10}

    with pytest.raises(ValueError, match="excluded_tickers"):
        preload_for_action_drafting(
            user_id="user_123",
            requested_trade=requested_trade,
            firestore_client=mock_fs,
        )


def test_preload_research_empty_question_raises():
    with pytest.raises(ValueError, match="research_question is required"):
        preload_for_research("user_123", "")
    with pytest.raises(ValueError, match="research_question is required"):
        preload_for_research("user_123", "   ")


def test_preload_research_valid_question_returns_dict():
    result = preload_for_research("user_123", "  What is the outlook for tech stocks in 2026?  ")
    assert result == {
        "user_id": "user_123",
        "research_question": "What is the outlook for tech stocks in 2026?",
    }


def test_preload_reviewer_success(sample_ips, sample_holdings):
    mock_fs = MagicMock()
    mock_fs.get_active_ips_by_user.return_value = sample_ips
    mock_fs.get_holdings.return_value = sample_holdings

    action_dict = {"action_id": "act_1", "ticker": "AAPL", "side": "buy", "quantity": 10.0}
    res = preload_for_reviewer("user_123", action=action_dict, firestore_client=mock_fs)
    assert res["user_id"] == "user_123"
    assert res["action"] == action_dict
    assert "ips" in res
    assert "holdings" in res


def test_preload_reviewer_no_ips_declines():
    mock_fs = MagicMock()
    mock_fs.get_active_ips_by_user.return_value = None

    with pytest.raises(PreloadDeclinedError, match="No active IPS found"):
        preload_for_reviewer("user_123", action={"action_id": "act_1"}, firestore_client=mock_fs)


def test_preload_reviewer_missing_action_raises():
    with pytest.raises(ValueError, match="requires 'action'"):
        preload_for_reviewer("user_123", action=None)


def test_preload_spending_facts_window_months_differentiation(sample_holdings):
    mock_bq = MagicMock()
    mock_bq.get_spending_snapshot.return_value = (
        {"total_income": 18000.0, "total_outflow": 12000.0},
        [],
    )

    mock_fs = MagicMock()
    mock_fs.get_holdings.return_value = sample_holdings

    facts_3 = preload_spending_facts("user_123", window_months=3, bq_client=mock_bq, firestore_client=mock_fs)
    facts_6 = preload_spending_facts("user_123", window_months=6, bq_client=mock_bq, firestore_client=mock_fs)

    assert facts_3["window_months"] == 3
    assert facts_6["window_months"] == 6
    assert facts_3["reserve_months"] != facts_6["reserve_months"]
    assert facts_3 != facts_6
