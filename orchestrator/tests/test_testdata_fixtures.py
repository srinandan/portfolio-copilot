"""Validates canonical test data fixtures against schemas and acceptance criteria."""

import csv
import json
from pathlib import Path

import jsonschema

from orchestrator.contracts import (
    HoldingsSnapshot,
    InvestmentPolicyStatement,
    LiabilitiesSnapshot,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TESTDATA_DIR = REPO_ROOT / "testdata"
SCHEMAS_DIR = REPO_ROOT / "schemas"


def load_json(filename: str):
    path = TESTDATA_DIR / filename
    assert path.exists(), f"Missing fixture: {path}"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_schema(filename: str):
    path = SCHEMAS_DIR / filename
    assert path.exists(), f"Missing schema: {path}"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_holdings_fixture_validates_and_parses():
    data = load_json("holdings.json")
    schema = load_schema("holdings.schema.json")
    jsonschema.validate(instance=data, schema=schema)

    holdings = HoldingsSnapshot.model_validate(data)
    assert holdings.user_id == "demo_user"
    assert holdings.total_value_usd == 200000.0
    assert holdings.cash_usd == 20000.0

    # Verify positions exist across multiple asset classes
    asset_classes = {p.asset_class for p in holdings.positions}
    assert "Equity" in asset_classes
    assert "Bonds" in asset_classes
    assert "Crypto" in asset_classes  # Unclassified asset class for IPS bands


def test_liabilities_fixture_validates_and_parses():
    data = load_json("liabilities.json")
    schema = load_schema("liabilities.schema.json")
    jsonschema.validate(instance=data, schema=schema)

    liabilities = LiabilitiesSnapshot.model_validate(data)
    assert liabilities.user_id == "demo_user"
    assert liabilities.total_liabilities_usd == 338500.0

    # Verify at least one high-interest liability (>15% APR)
    high_interest_liabs = [
        liab for liab in liabilities.liabilities if liab.interest_rate_percent and liab.interest_rate_percent > 15.0
    ]
    assert len(high_interest_liabs) >= 1
    assert high_interest_liabs[0].type == "credit_card"
    assert high_interest_liabs[0].interest_rate_percent == 24.99


def test_ips_fixture_validates_and_parses():
    data = load_json("ips.json")
    schema = load_schema("ips.schema.json")
    jsonschema.validate(instance=data, schema=schema)

    ips = InvestmentPolicyStatement.model_validate(data)
    assert ips.user_id == "demo_user"
    assert ips.status == "active"
    assert ips.constraints.concentration_limit_percent == 15.0
    assert "TSLA" in ips.constraints.excluded_tickers
    assert "Energy" in ips.constraints.excluded_sectors

    # Realistic approval thresholds
    assert ips.approval_required_above_usd == 25000.0
    assert ips.approval_required_above_percent == 20.0


def test_fixtures_are_internally_consistent():
    ips_data = load_json("ips.json")
    holdings_data = load_json("holdings.json")
    poisoned_data = load_json("poisoned_research.json")

    ips_asset_classes = {band["asset_class"] for band in ips_data["target_allocation"]}
    holding_asset_classes = {p["asset_class"] for p in holdings_data["positions"]}

    # IPS asset classes appear in holdings
    for ac in ["Equity", "Bonds"]:
        assert ac in holding_asset_classes
        assert ac in ips_asset_classes

    # At least one position matches NONE of the IPS bands (unclassified)
    unclassified = [p for p in holdings_data["positions"] if p["asset_class"] not in ips_asset_classes]
    assert len(unclassified) >= 1
    assert unclassified[0]["ticker"] == "BTC"
    assert unclassified[0]["asset_class"] == "Crypto"

    # Out-of-band allocation: Equity total is $135k / $200k = 67.5%, exceeding max_percent 65%
    equity_value = sum(p["market_value_usd"] for p in holdings_data["positions"] if p["asset_class"] == "Equity")
    equity_percent = (equity_value / holdings_data["total_value_usd"]) * 100
    equity_band = next(b for b in ips_data["target_allocation"] if b["asset_class"] == "Equity")
    assert equity_percent > equity_band["max_percent"]

    # Poisoned research result targets a ticker that exists in holdings
    holding_tickers = {p["ticker"] for p in holdings_data["positions"]}
    assert poisoned_data["ticker"] in holding_tickers
    assert poisoned_data["suggested_allocation_percent"] > ips_data["constraints"]["concentration_limit_percent"]


def test_chase_transactions_csv_exercises_dual_condition_anomaly():
    csv_path = TESTDATA_DIR / "chase_transactions.csv"
    assert csv_path.exists()

    monthly_spend: dict[str, dict[str, float]] = {}  # month -> category -> total spend

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            month = row["transaction_date"][:7]  # YYYY-MM
            cat = row["normalized_category"]
            amount = float(row["amount"])
            if amount < 0:  # outflow / spend
                monthly_spend.setdefault(month, {}).setdefault(cat, 0.0)
                monthly_spend[month][cat] += abs(amount)

    months = sorted(monthly_spend.keys())
    assert len(months) == 4, "Expected 4 months of transactions (3 trailing + 1 current)"
    trailing_months = months[:3]
    current_month = months[3]

    # Check dining anomaly: avg M1-M3 = 300, M4 = 650.
    dining_trailing_avg = sum(monthly_spend[m].get("dining", 0.0) for m in trailing_months) / 3.0
    dining_curr = monthly_spend[current_month].get("dining", 0.0)
    assert dining_trailing_avg == 300.0
    assert dining_curr == 650.0
    # Rule 1: current > trailing * 1.4 (650 > 420)
    # Rule 2: current > trailing + 100 (650 > 400)
    assert dining_curr > (dining_trailing_avg * 1.4)
    assert dining_curr > (dining_trailing_avg + 100.0)

    # Check subscriptions: avg M1-M3 = 15.0, M4 = 35.0.
    sub_trailing_avg = sum(monthly_spend[m].get("subscriptions", 0.0) for m in trailing_months) / 3.0
    sub_curr = monthly_spend[current_month].get("subscriptions", 0.0)
    assert sub_trailing_avg == 15.0
    assert sub_curr == 35.0
    # Rule 1 is met: 35 > 15 * 1.4 = 21 (133% increase)
    assert sub_curr > (sub_trailing_avg * 1.4)
    # Rule 2 is NOT met: 35 <= 15 + 100 = 115 (so does not trip dual-condition anomaly)
    assert not (sub_curr > (sub_trailing_avg + 100.0))
