from datetime import date, datetime, timezone

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
from orchestrator.skills.portfolio_analysis.logic import calculate_drift


@pytest.fixture
def sample_ips():
    return InvestmentPolicyStatement(
        ips_id="ips_1",
        user_id="user_1",
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
        constraints=Constraints(concentration_limit_percent=15),
        rebalancing_rules=RebalancingRules(drift_threshold_percent=5.0),
        created_at=datetime.now(timezone.utc)
    )

@pytest.fixture
def sample_holdings():
    return HoldingsSnapshot(
        user_id="user_1",
        as_of=datetime.now(timezone.utc),
        positions=[
            Position(ticker="VTI", quantity=100, asset_class="Equity", market_value_usd=60000),
            Position(ticker="BND", quantity=100, asset_class="Fixed Income", market_value_usd=30000),
        ],
        cash_usd=10000,
        total_value_usd=100000
    )


def test_basic_drift_calculation_in_band(sample_holdings, sample_ips):
    report = calculate_drift(sample_holdings, sample_ips)

    assert report.rebalance_recommended is False
    assert report.unclassified_value_usd == 0.0

    # Check entries
    entry_map = {e.asset_class: e for e in report.entries}
    assert entry_map["Equity"].current_percent == 60.0
    assert entry_map["Equity"].in_band is True
    assert entry_map["Equity"].drift_amount_percent == 0.0

    assert entry_map["Fixed Income"].current_percent == 30.0
    assert entry_map["Fixed Income"].in_band is True

    assert entry_map["Cash"].current_percent == 10.0
    assert entry_map["Cash"].in_band is True


def test_out_of_band_but_below_threshold(sample_holdings, sample_ips):
    # Drift threshold is 5.0
    # Let's drift Equity to 72% (2% out of band, which is < 5%)
    # Target: 60, Max: 70
    sample_holdings.positions[0].market_value_usd = 72000
    sample_holdings.positions[1].market_value_usd = 18000
    # Cash remains 10000

    report = calculate_drift(sample_holdings, sample_ips)

    assert report.rebalance_recommended is False
    entry_map = {e.asset_class: e for e in report.entries}

    assert entry_map["Equity"].current_percent == 72.0
    assert entry_map["Equity"].in_band is False
    assert entry_map["Equity"].drift_amount_percent == 2.0

    assert entry_map["Fixed Income"].current_percent == 18.0
    assert entry_map["Fixed Income"].in_band is False
    assert entry_map["Fixed Income"].drift_amount_percent == 2.0


def test_exactly_at_threshold_triggers_rebalance(sample_holdings, sample_ips):
    # Drift threshold is 5.0
    # Equity max is 70.0. We want drift amount to be exactly 5.0, so current_percent = 75.0
    sample_holdings.positions[0].market_value_usd = 75000
    sample_holdings.positions[1].market_value_usd = 15000

    report = calculate_drift(sample_holdings, sample_ips)

    assert report.rebalance_recommended is True
    entry_map = {e.asset_class: e for e in report.entries}

    assert entry_map["Equity"].current_percent == 75.0
    assert entry_map["Equity"].drift_amount_percent == 5.0


def test_unclassified_assets_reporting(sample_holdings, sample_ips):
    # Add gold and crypto
    sample_holdings.positions.append(
        Position(ticker="GLD", quantity=10, asset_class="Alternatives", market_value_usd=10000)
    )
    sample_holdings.positions.append(
        Position(ticker="BTC", quantity=1, asset_class="Crypto", market_value_usd=5000)
    )
    # Total is now 115000
    sample_holdings.total_value_usd = 115000

    report = calculate_drift(sample_holdings, sample_ips)

    assert report.unclassified_value_usd == 15000.0

    # Check percentages relative to true total
    entry_map = {e.asset_class: e for e in report.entries}

    expected_equity_percent = (60000 / 115000) * 100
    assert abs(entry_map["Equity"].current_percent - expected_equity_percent) < 0.001


def test_missing_drift_threshold(sample_holdings, sample_ips):
    # If no drift threshold, it should not recommend rebalance even if out of band
    sample_ips.rebalancing_rules.drift_threshold_percent = None

    # Make it out of band by a lot
    sample_holdings.positions[0].market_value_usd = 90000
    sample_holdings.positions[1].market_value_usd = 0

    report = calculate_drift(sample_holdings, sample_ips)

    assert report.rebalance_recommended is False

    entry_map = {e.asset_class: e for e in report.entries}
    assert entry_map["Equity"].in_band is False
    assert entry_map["Equity"].drift_amount_percent == 20.0  # 90 - 70 = 20

def test_zero_total_value(sample_holdings, sample_ips):
    sample_holdings.total_value_usd = 0
    sample_holdings.positions = []
    sample_holdings.cash_usd = 0

    report = calculate_drift(sample_holdings, sample_ips)

    assert report.rebalance_recommended is False
    assert report.unclassified_value_usd == 0.0
    entry_map = {e.asset_class: e for e in report.entries}
    assert entry_map["Equity"].current_percent == 0.0
    assert entry_map["Equity"].drift_amount_percent == 50.0  # min is 50, current is 0
