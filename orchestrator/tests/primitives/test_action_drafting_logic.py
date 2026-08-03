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
from orchestrator.contracts.proposed_action import Side
from orchestrator.primitives.action_drafting import calculate_draft_action


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
    assert action["side"] == Side.SELL
    assert abs(action["estimated_value_usd"] - 7000.0) < 0.01
    assert abs(action["quantity"] - (7000.0 / 150.0)) < 0.01
    assert "exactly 60.0%" in action["rationale"]


def test_trim_insufficient_shares_in_largest_position_raises():
    """Verifies B1: If largest position cannot cover entire trim, skill declines with ValueError."""
    ips = get_base_ips()
    # Let's say Equity target is 10%, current Equity is $25k on $30k (needs $22k trim)
    ips.target_allocation[0].target_percent = 10.0
    ips.target_allocation[0].max_percent = 20.0
    # Largest position AAPL only has $15k (100 shares @ $150)
    holdings = get_base_holdings()
    drift_report = {"rebalance_recommended": True}

    with pytest.raises(ValueError, match="no single position in Equity has enough market value to complete the trim"):
        calculate_draft_action(drift_report, holdings, ips)


def test_direct_requested_trade():
    ips = get_base_ips()
    # Set limit to 20% so 2k purchase on 30k (6.67%) passes concentration
    ips.constraints.concentration_limit_percent = 20.0
    holdings = get_base_holdings()
    drift_report = {"requested_trade": {"ticker": "TSLA", "side": "buy", "quantity": 10}}

    action = calculate_draft_action(drift_report, holdings, ips)
    assert action is not None
    assert action["ticker"] == "TSLA"
    assert action["side"] == Side.BUY
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


def test_concentration_limit_on_buy_with_existing_position():
    """Verifies B2/B3: Buying more of an existing position that pushes total over limit is blocked."""
    ips = get_base_ips()
    ips.constraints.concentration_limit_percent = 15.0  # $4,500 max
    # Existing NVDA is $3,000 (10% of 30k)
    holdings = HoldingsSnapshot(
        user_id="user_123",
        as_of=datetime.now(timezone.utc),
        positions=[
            Position(ticker="NVDA", quantity=30, asset_class="Equity", market_value_usd=3000),
            Position(ticker="BND", quantity=270, asset_class="Bonds", market_value_usd=27000),
        ],
        cash_usd=0.0,
        total_value_usd=30000.0,
    )
    # Buy 20 more NVDA @ $100 = $2,000 -> new total $5,000 (16.67% > 15%)
    drift_report = {"requested_trade": {"ticker": "NVDA", "side": "buy", "quantity": 20}}

    with pytest.raises(ValueError, match="exceeding concentration limit of 15.0%"):
        calculate_draft_action(drift_report, holdings, ips)


def test_concentration_limit_on_sell_leaving_position_over_limit():
    """Verifies B2/B3: Selling that still leaves position above concentration limit raises ValueError."""
    ips = get_base_ips()
    ips.constraints.concentration_limit_percent = 15.0  # $4,500 max
    # Existing AAPL is $15,000 (50% of 30k)
    holdings = get_base_holdings()
    # Sell 10 shares of AAPL @ $150 = $1,500 -> remaining $13,500 (45% > 15%)
    drift_report = {"requested_trade": {"ticker": "AAPL", "side": "sell", "quantity": 10}}

    with pytest.raises(ValueError, match="exceeding concentration limit of 15.0%"):
        calculate_draft_action(drift_report, holdings, ips)


def test_custom_sector_and_quote_injection():
    """Verifies B4: Custom sector and quote lookup functions can be injected into calculate_draft_action."""
    ips = get_base_ips()
    ips.constraints.excluded_sectors = ["CustomRenewables"]
    holdings = get_base_holdings()
    drift_report = {"requested_trade": {"ticker": "CUSTOM_TICKER", "side": "buy", "quantity": 5}}

    def custom_quote(ticker: str) -> float:
        return 50.0

    def custom_sector(ticker: str) -> str:
        return "CustomRenewables"

    with pytest.raises(ValueError, match="excluded_sectors"):
        calculate_draft_action(
            drift_report,
            holdings,
            ips,
            quote_fn=custom_quote,
            sector_fn=custom_sector,
        )
