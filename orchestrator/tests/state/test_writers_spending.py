from unittest.mock import MagicMock

from orchestrator.contracts.spending_analysis import CategorySpending, SpendingAnomaly, SpendingReport
from orchestrator.state.writers import write_spending_report


def test_write_spending_report_persists_to_firestore():
    mock_client = MagicMock()
    report = SpendingReport(
        user_id="user_123",
        total_income_usd=10000.0,
        total_outflow_usd=6000.0,
        savings_rate=0.4,
        reserve_months=6.5,
        category_breakdown=[
            CategorySpending(category="housing", amount_usd=2500.0, percent_of_total=41.6, monthly_average_usd=2500.0),
            CategorySpending(
                category="groceries", amount_usd=1200.0, percent_of_total=20.0, monthly_average_usd=1100.0
            ),
        ],
        anomalies=[
            SpendingAnomaly(
                category="dining",
                amount_usd=1500.0,
                trailing_average_usd=800.0,
                description="Dining out exceeded average by $700",
                date="2026-08-01",
            )
        ],
        narrative_summary="Solid savings rate.",
    )

    write_spending_report(
        user_id="user_123",
        report=report,
        db_client=mock_client,
    )

    mock_client.set_spending_report.assert_called_once_with("user_123", report)


def test_spending_report_serialized_shape_matches_schema():
    import json
    from pathlib import Path

    import jsonschema

    from orchestrator.data.firestore import FirestoreClient

    client = FirestoreClient(project="test-project")
    report = SpendingReport(
        user_id="user_123",
        total_income_usd=10000.0,
        total_outflow_usd=6000.0,
        savings_rate=0.4,
        reserve_months=6.5,
        category_breakdown=[
            CategorySpending(category="housing", amount_usd=2500.0, percent_of_total=41.6, monthly_average_usd=2500.0),
        ],
        anomalies=[
            SpendingAnomaly(
                category="dining",
                amount_usd=1500.0,
                trailing_average_usd=800.0,
                description="Dining out exceeded average by $700",
                date="2026-08-01",
            )
        ],
        narrative_summary="Solid savings rate.",
    )

    serialized = client._dict_factory(report)
    assert "percent_of_total" in serialized["category_breakdown"][0]
    assert "amount_usd" in serialized["anomalies"][0]
    assert "trailing_average_usd" in serialized["anomalies"][0]
    assert serialized["anomalies"][0]["date"] == "2026-08-01"

    schema_path = Path(__file__).resolve().parent.parent.parent.parent / "schemas" / "spending-report.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    jsonschema.validate(instance=serialized, schema=schema)
