from datetime import date, datetime, timezone

import pytest

from orchestrator.contracts.drift_report import DriftReport, DriftReportEntry
from orchestrator.contracts.holdings import HoldingsSnapshot, Position
from orchestrator.contracts.ips import (
    Constraints,
    InvestmentPolicyStatement,
    IPSStatus,
    RebalancingRules,
    RiskTolerance,
    TargetAllocation,
)
from orchestrator.primitives.portfolio_analysis import calculate_drift


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
        created_at=datetime.now(timezone.utc),
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
        total_value_usd=100000,
    )


def test_calculate_drift_returns_contracts_drift_report(sample_holdings, sample_ips):
    report = calculate_drift(sample_holdings, sample_ips)
    assert isinstance(report, DriftReport)
    assert all(isinstance(entry, DriftReportEntry) for entry in report.entries)


def test_calculate_drift_in_band(sample_holdings, sample_ips):
    report = calculate_drift(sample_holdings, sample_ips)

    assert len(report.entries) == 3
    assert report.unclassified_value_usd == 0.0
    assert report.rebalance_recommended is False

    entry_map = {e.asset_class: e for e in report.entries}
    assert entry_map["Equity"].current_percent == 60.0
    assert entry_map["Equity"].in_band is True
    assert entry_map["Equity"].drift_amount_percent == 0.0

    assert entry_map["Fixed Income"].current_percent == 30.0
    assert entry_map["Fixed Income"].in_band is True

    assert entry_map["Cash"].current_percent == 10.0
    assert entry_map["Cash"].in_band is True


def test_calculate_drift_out_of_band(sample_ips):
    # Total value: 100,000
    # Equity: 80,000 (80%) -> target 60%, max 70% -> drift 10%
    # Fixed Income: 15,000 (15%) -> target 30%, min 20% -> drift 5%
    # Cash: 5,000 (5%) -> target 10%, min 5% -> in band
    holdings = HoldingsSnapshot(
        user_id="user_1",
        as_of=datetime.now(timezone.utc),
        positions=[
            Position(ticker="VTI", quantity=100, asset_class="Equity", market_value_usd=80000),
            Position(ticker="BND", quantity=100, asset_class="Fixed Income", market_value_usd=15000),
        ],
        cash_usd=5000,
        total_value_usd=100000,
    )

    report = calculate_drift(holdings, sample_ips)

    assert report.rebalance_recommended is True

    entry_map = {e.asset_class: e for e in report.entries}
    assert entry_map["Equity"].current_percent == 80.0
    assert entry_map["Equity"].in_band is False
    assert entry_map["Equity"].drift_amount_percent == 10.0

    assert entry_map["Fixed Income"].current_percent == 15.0
    assert entry_map["Fixed Income"].in_band is False
    assert entry_map["Fixed Income"].drift_amount_percent == 5.0

    assert entry_map["Cash"].current_percent == 5.0
    assert entry_map["Cash"].in_band is True
    assert entry_map["Cash"].drift_amount_percent == 0.0


def test_calculate_drift_unclassified_assets(sample_ips):
    # Total value: 110,000
    # Crypto position not in IPS target allocations
    holdings = HoldingsSnapshot(
        user_id="user_1",
        as_of=datetime.now(timezone.utc),
        positions=[
            Position(ticker="VTI", quantity=100, asset_class="Equity", market_value_usd=60000),
            Position(ticker="BND", quantity=100, asset_class="Fixed Income", market_value_usd=30000),
            Position(ticker="BTC", quantity=1, asset_class="Crypto", market_value_usd=10000),
        ],
        cash_usd=10000,
        total_value_usd=110000,
    )

    report = calculate_drift(holdings, sample_ips)

    assert report.unclassified_value_usd == 10000.0


def test_calculate_drift_empty_portfolio(sample_ips):
    holdings = HoldingsSnapshot(
        user_id="user_1",
        as_of=datetime.now(timezone.utc),
        positions=[],
        cash_usd=0.0,
        total_value_usd=0.0,
    )

    report = calculate_drift(holdings, sample_ips)

    assert report.unclassified_value_usd == 0.0
    assert report.rebalance_recommended is False
    for entry in report.entries:
        assert entry.current_percent == 0.0


def test_calculate_drift_rebalance_trigger_threshold():
    # IPS with drift threshold of 3.0%
    ips = InvestmentPolicyStatement(
        ips_id="ips_2",
        user_id="user_2",
        version=1,
        status=IPSStatus.ACTIVE,
        effective_date=date(2023, 1, 1),
        risk_tolerance=RiskTolerance.MODERATE,
        time_horizon_years=10,
        target_allocation=[
            TargetAllocation(asset_class="Equity", target_percent=60.0, min_percent=55.0, max_percent=65.0),
            TargetAllocation(asset_class="Cash", target_percent=40.0, min_percent=35.0, max_percent=45.0),
        ],
        constraints=Constraints(concentration_limit_percent=15),
        rebalancing_rules=RebalancingRules(drift_threshold_percent=3.0),
        created_at=datetime.now(timezone.utc),
    )

    # Drift is 2% (outside band 55-65 -> at 67%), below threshold 3% -> rebalance_recommended False
    holdings = HoldingsSnapshot(
        user_id="user_2",
        as_of=datetime.now(timezone.utc),
        positions=[Position(ticker="VTI", quantity=100, asset_class="Equity", market_value_usd=67000)],
        cash_usd=33000,
        total_value_usd=100000,
    )
    report = calculate_drift(holdings, ips)
    assert report.rebalance_recommended is False

    # Drift is 3% (at 68%) -> >= threshold 3% -> rebalance_recommended True
    holdings_higher = HoldingsSnapshot(
        user_id="user_2",
        as_of=datetime.now(timezone.utc),
        positions=[Position(ticker="VTI", quantity=100, asset_class="Equity", market_value_usd=68000)],
        cash_usd=32000,
        total_value_usd=100000,
    )
    report_higher = calculate_drift(holdings_higher, ips)
    assert report_higher.rebalance_recommended is True


def test_cash_asset_class_synonym_mapping():
    ips = InvestmentPolicyStatement(
        ips_id="ips_synonym",
        user_id="user_syn",
        version=1,
        status=IPSStatus.ACTIVE,
        effective_date=date(2023, 1, 1),
        risk_tolerance=RiskTolerance.CONSERVATIVE,
        time_horizon_years=3,
        target_allocation=[
            TargetAllocation(asset_class="Equity", target_percent=50.0, min_percent=40.0, max_percent=60.0),
            TargetAllocation(asset_class="cash_reserves", target_percent=50.0, min_percent=40.0, max_percent=60.0),
        ],
        constraints=Constraints(concentration_limit_percent=15),
        created_at=datetime.now(timezone.utc),
    )

    holdings = HoldingsSnapshot(
        user_id="user_syn",
        as_of=datetime.now(timezone.utc),
        positions=[Position(ticker="VTI", quantity=100, asset_class="Equity", market_value_usd=50000)],
        cash_usd=50000,
        total_value_usd=100000,
    )

    report = calculate_drift(holdings, ips)
    entry_map = {e.asset_class: e for e in report.entries}
    assert entry_map["cash_reserves"].current_percent == 50.0
    assert entry_map["cash_reserves"].in_band is True
    assert report.unclassified_value_usd == 0.0


def test_cash_position_and_cash_usd_deduplication(sample_ips):
    holdings = HoldingsSnapshot(
        user_id="user_dedup",
        as_of=datetime.now(timezone.utc),
        positions=[
            Position(ticker="VTI", quantity=100, asset_class="Equity", market_value_usd=60000),
            Position(ticker="BND", quantity=100, asset_class="Fixed Income", market_value_usd=30000),
            Position(ticker="USD", quantity=10000, asset_class="Cash", market_value_usd=10000),
        ],
        cash_usd=10000,
        total_value_usd=100000,
    )

    report = calculate_drift(holdings, sample_ips)
    entry_map = {e.asset_class: e for e in report.entries}

    assert entry_map["Cash"].current_percent == 10.0
    assert entry_map["Cash"].in_band is True
    assert report.rebalance_recommended is False


def test_stale_total_value_usd_reconciled(sample_ips):
    holdings = HoldingsSnapshot(
        user_id="user_reconcile",
        as_of=datetime.now(timezone.utc),
        positions=[
            Position(ticker="VTI", quantity=100, asset_class="Equity", market_value_usd=60000),
            Position(ticker="BND", quantity=100, asset_class="Fixed Income", market_value_usd=30000),
        ],
        cash_usd=10000,
        total_value_usd=50000,
    )

    report = calculate_drift(holdings, sample_ips)
    entry_map = {e.asset_class: e for e in report.entries}

    assert entry_map["Equity"].current_percent == 60.0
    assert entry_map["Fixed Income"].current_percent == 30.0
    assert entry_map["Cash"].current_percent == 10.0
    assert report.rebalance_recommended is False
