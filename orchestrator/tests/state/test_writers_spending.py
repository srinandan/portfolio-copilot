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
            CategorySpending(category="housing", amount_usd=2500.0, percentage=41.6),
            CategorySpending(category="groceries", amount_usd=1200.0, percentage=20.0),
        ],
        anomalies=[
            SpendingAnomaly(
                category="dining",
                current_spend_usd=1500.0,
                trailing_avg_usd=800.0,
                description="Dining out exceeded average by $700",
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
