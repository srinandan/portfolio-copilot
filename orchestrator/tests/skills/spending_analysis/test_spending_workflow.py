from unittest.mock import MagicMock, patch

import pytest
from google.adk import Context
from google.adk.events import RequestInput

from orchestrator.skills.spending_analysis.__init__ import spending_analysis_skill


@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=Context)
    return ctx

@pytest.mark.asyncio
@patch('orchestrator.skills.spending_analysis.__init__.FirestoreClient')
@patch('orchestrator.skills.spending_analysis.__init__.BigQueryClient')
async def test_spending_analysis_skill_savings_rate(mock_bq_class, mock_fs_class, mock_context):
    mock_fs = mock_fs_class.return_value
    mock_bq = mock_bq_class.return_value

    mock_bq.get_trailing_income_and_outflow.return_value = {
        "total_income": 5000.0,
        "total_outflow": 3000.0
    }

    mock_holdings = MagicMock()
    mock_holdings.cash_usd = 10000.0
    mock_fs.get_holdings.return_value = mock_holdings

    node_input = {
        "user_id": "user1",
        "query_intent": "savings_rate"
    }

    generator = spending_analysis_skill._func(mock_context, node_input)
    result = await generator.__anext__()

    assert result["savings_rate"] == 0.4
    assert result["reserve_months"] == 10.0

@pytest.mark.asyncio
@patch('orchestrator.skills.spending_analysis.__init__.FirestoreClient')
@patch('orchestrator.skills.spending_analysis.__init__.BigQueryClient')
async def test_spending_analysis_skill_anomaly_check(mock_bq_class, mock_fs_class, mock_context):
    mock_bq = mock_bq_class.return_value

    mock_bq.get_monthly_spending_totals.return_value = [
        {"normalized_category": "dining", "current_month_spend": 500, "trailing_3mo_avg": 300},
        {"normalized_category": "entertainment", "current_month_spend": 35, "trailing_3mo_avg": 20},
    ]

    node_input = {
        "user_id": "user1",
        "query_intent": "anomaly_check"
    }

    generator = spending_analysis_skill._func(mock_context, node_input)
    result = await generator.__anext__()

    assert "anomalies" in result
    assert len(result["anomalies"]) == 1
    assert result["anomalies"][0]["category"] == "dining"

@pytest.mark.asyncio
@patch('orchestrator.skills.spending_analysis.__init__.FirestoreClient')
@patch('orchestrator.skills.spending_analysis.__init__.BigQueryClient')
async def test_spending_analysis_skill_ad_hoc_valid(mock_bq_class, mock_fs_class, mock_context):
    mock_bq = mock_bq_class.return_value

    mock_bq.validate_and_execute_nl_sql.return_value = [{"col": "val"}]

    node_input = {
        "user_id": "user1",
        "query_intent": "ad_hoc",
        "sql_query": "SELECT * FROM chase_transactions WHERE user_id = @user_id"
    }

    generator = spending_analysis_skill._func(mock_context, node_input)
    result = await generator.__anext__()

    assert "results" in result
    assert result["results"] == [{"col": "val"}]

@pytest.mark.asyncio
@patch('orchestrator.skills.spending_analysis.__init__.FirestoreClient')
@patch('orchestrator.skills.spending_analysis.__init__.BigQueryClient')
async def test_spending_analysis_skill_ad_hoc_missing_query(mock_bq_class, mock_fs_class, mock_context):
    node_input = {
        "user_id": "user1",
        "query_intent": "ad_hoc",
    }

    generator = spending_analysis_skill._func(mock_context, node_input)
    result = await generator.__anext__()

    assert isinstance(result, RequestInput)
