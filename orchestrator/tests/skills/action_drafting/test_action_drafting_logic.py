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
from orchestrator.skills.action_drafting.logic import calculate_draft_action


def get_base_ips():
    return InvestmentPolicyStatement(
        ips_id="ips_123",
        user_id="user_123",
        version=1,
        status=IPSStatus.ACTIVE,
        effective_date="2024-01-01",
        risk_tolerance=RiskTolerance.MODERATE,
        time_horizon_years=10,
        target_allocation=[
            TargetAllocation(asset_class="Equity", target_percent=60, min_percent=50, max_percent=70),
            TargetAllocation(asset_class="Bonds", target_percent=40, min_percent=30, max_percent=50),
        ],
        constraints=Constraints(concentration_limit_percent=15),
        created_at=datetime.now(timezone.utc),
    )


def get_base_holdings():
    return HoldingsSnapshot(
        user_id="user_123",
        as_of=datetime.now(timezone.utc),
        positions=[
            Position(ticker="AAPL", quantity=100, asset_class="Equity", market_value_usd=15000),  # 15k
            Position(ticker="MSFT", quantity=50, asset_class="Equity", market_value_usd=10000),  # 10k
            Position(ticker="BND", quantity=100, asset_class="Bonds", market_value_usd=5000),  # 5k
        ],
        cash_usd=0.0,
        total_value_usd=30000.0,
    )


def test_no_rebalance_warranted():
    ips = get_base_ips()
    holdings = get_base_holdings()
    # Current Equity is 25k/30k = 83.3% > 70% max, but drift report says False
    drift_report = {"rebalance_recommended": False}

    action = calculate_draft_action(drift_report, holdings, ips)
    assert action is None


def test_trim_exact_quantity():
    ips = get_base_ips()
    holdings = get_base_holdings()
    # Equity: 25,000 / 30,000 = 83.33%
    # Target: 60% of 30,000 = 18,000
    # Trim amount = 25,000 - 18,000 = 7,000
    # Largest position in Equity is AAPL (15k)
    # Mock price of AAPL is 150
    # Quantity to sell = 7000 / 150 = 46.666...
    drift_report = {"rebalance_recommended": True}

    action = calculate_draft_action(drift_report, holdings, ips)
    assert action is not None
    assert action["ticker"] == "AAPL"
    assert action["side"] == "sell"
    assert action["order_type"] == "market"
    assert abs(action["estimated_value_usd"] - 7000.0) < 0.01
    assert abs(action["quantity"] - (7000.0 / 150.0)) < 0.01
    assert "exactly 60.0%" in action["rationale"]


def test_direct_requested_trade():
    ips = get_base_ips()
    holdings = get_base_holdings()
    drift_report = {"requested_trade": {"ticker": "TSLA", "side": "buy", "quantity": 10}}

    action = calculate_draft_action(drift_report, holdings, ips)
    assert action is not None
    assert action["ticker"] == "TSLA"
    assert action["side"] == "buy"
    assert action["quantity"] == 10
    assert action["estimated_price_usd"] == 200.0
    assert action["estimated_value_usd"] == 2000.0


def test_excluded_ticker_constraint():
    ips = get_base_ips()
    ips.constraints.excluded_tickers = ["AAPL"]
    holdings = get_base_holdings()
    drift_report = {"rebalance_recommended": True}

    with pytest.raises(ValueError, match="excluded_tickers"):
        calculate_draft_action(drift_report, holdings, ips)


def test_excluded_sector_constraint():
    ips = get_base_ips()
    ips.constraints.excluded_sectors = ["Technology"]
    holdings = get_base_holdings()
    drift_report = {"rebalance_recommended": True}

    with pytest.raises(ValueError, match="excluded_sectors"):
        calculate_draft_action(drift_report, holdings, ips)


def test_concentration_limit_constraint():
    ips = get_base_ips()
    # Concentration limit is 15% (i.e. 4500 on 30k total)
    holdings = get_base_holdings()
    # Requesting to buy 30 shares of TSLA (30*200 = 6000 -> 20%)
    drift_report = {"requested_trade": {"ticker": "TSLA", "side": "buy", "quantity": 30}}

    with pytest.raises(ValueError, match="concentration limit"):
        calculate_draft_action(drift_report, holdings, ips)
