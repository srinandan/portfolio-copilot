from unittest.mock import MagicMock, patch

import pytest

from src.orchestrator.data.bigquery import BigQueryClient


@patch("google.cloud.bigquery.Client")
def test_validate_and_execute_nl_sql_valid_query_mcp(mock_client):
    client = BigQueryClient("test-project", enable_mcp=True)
    mock_mcp = MagicMock()
    mock_mcp.execute_query.return_value = [{"col": 1}]
    client._mcp_client = mock_mcp

    result = client.validate_and_execute_nl_sql(
        "user123", "SELECT * FROM checking_transactions WHERE user_id = @user_id"
    )
    assert result == [{"col": 1}]
    mock_mcp.execute_query.assert_called_once()


@patch("google.cloud.bigquery.Client")
def test_validate_and_execute_nl_sql_fallback_to_direct_on_mcp_failure(mock_client):
    client = BigQueryClient("test-project", enable_mcp=True)
    mock_mcp = MagicMock()
    mock_mcp.execute_query.side_effect = RuntimeError("MCP endpoint down")
    client._mcp_client = mock_mcp

    client.client = MagicMock()
    mock_job = MagicMock()
    mock_job.result.return_value = [{"col": 2}]
    client.client.query.return_value = mock_job

    result = client.validate_and_execute_nl_sql(
        "user123", "SELECT * FROM checking_transactions WHERE user_id = @user_id"
    )
    assert result == [{"col": 2}]
    client.client.query.assert_called_once()


@patch("google.cloud.bigquery.Client")
def test_validate_and_execute_nl_sql_direct_mode(mock_client):
    client = BigQueryClient("test-project", enable_mcp=False)
    assert client._mcp_client is None

    client.client = MagicMock()
    mock_job = MagicMock()
    mock_job.result.return_value = [{"col": 3}]
    client.client.query.return_value = mock_job

    result = client.validate_and_execute_nl_sql(
        "user123", "SELECT * FROM checking_transactions WHERE user_id = @user_id"
    )
    assert result == [{"col": 3}]


@pytest.mark.parametrize(
    "query, error_msg",
    [
        ("UPDATE checking_transactions SET amount = 0 WHERE user_id = @user_id", "Write-intent SQL refused"),
        ("DELETE FROM checking_transactions WHERE user_id = @user_id", "Write-intent SQL refused"),
        ("SELECT * FROM some_other_table WHERE user_id = @user_id", "must target a transactions table"),
        ("SELECT * FROM checking_transactions WHERE amount > 0", "must include @user_id parameter"),
    ],
)
@patch("google.cloud.bigquery.Client")
def test_validate_and_execute_nl_sql_invalid_queries(mock_client, query, error_msg):
    client = BigQueryClient("test-project")

    with pytest.raises(ValueError) as excinfo:
        client.validate_and_execute_nl_sql("user123", query)

    assert error_msg in str(excinfo.value)


@pytest.mark.parametrize("window", [3, 6])
@patch("google.cloud.bigquery.Client")
def test_get_trailing_income_and_outflow_uses_parameterized_window(mock_client_cls, window):
    client = BigQueryClient("test-project", enable_mcp=False)
    client.client = MagicMock()
    mock_job = MagicMock()
    mock_row = MagicMock()
    mock_row.total_income = 5000.0
    mock_row.total_outflow = 3000.0
    mock_job.result.return_value = [mock_row]
    client.client.query.return_value = mock_job

    res = client.get_trailing_income_and_outflow("user123", "2026-08-01", window_months=window)

    args, kwargs = client.client.query.call_args
    sql = args[0]
    job_config = kwargs["job_config"]
    assert "INTERVAL @window_months MONTH" in sql
    window_param = [p for p in job_config.query_parameters if p.name == "window_months"][0]
    assert window_param.value == window
    assert res == {"total_income": 5000.0, "total_outflow": 3000.0}


@pytest.mark.parametrize("window", [3, 6])
@patch("google.cloud.bigquery.Client")
def test_get_monthly_spending_totals_uses_parameterized_window(mock_client_cls, window):
    client = BigQueryClient("test-project", enable_mcp=False)
    client.client = MagicMock()
    mock_job = MagicMock()
    mock_job.result.return_value = []
    client.client.query.return_value = mock_job

    client.get_monthly_spending_totals("user123", "2026-08-01", window_months=window)

    args, kwargs = client.client.query.call_args
    sql = args[0]
    job_config = kwargs["job_config"]
    assert "INTERVAL @window_months MONTH" in sql
    window_param = [p for p in job_config.query_parameters if p.name == "window_months"][0]
    assert window_param.value == window


@pytest.mark.parametrize("window", [3, 6])
@patch("google.cloud.bigquery.Client")
def test_get_spending_snapshot_uses_parameterized_window(mock_client_cls, window):
    client = BigQueryClient("test-project", enable_mcp=False)
    client.client = MagicMock()
    mock_job = MagicMock()
    mock_row = MagicMock()
    mock_row.total_income = 10000.0
    mock_row.total_outflow = 4000.0
    mock_row.category_totals = [
        {"normalized_category": "dining", "current_month_spend": 200.0, "trailing_3mo_avg": 180.0}
    ]
    mock_job.result.return_value = [mock_row]
    client.client.query.return_value = mock_job

    totals, categories = client.get_spending_snapshot("user123", "2026-08-01", window_months=window)

    args, kwargs = client.client.query.call_args
    sql = args[0]
    job_config = kwargs["job_config"]
    assert "INTERVAL @window_months MONTH" in sql
    window_param = [p for p in job_config.query_parameters if p.name == "window_months"][0]
    assert window_param.value == window
    assert totals == {"total_income": 10000.0, "total_outflow": 4000.0}
    assert len(categories) == 1
    assert categories[0]["normalized_category"] == "dining"


@patch("google.cloud.bigquery.Client")
def test_get_spending_snapshot_empty_results(mock_client_cls):
    client = BigQueryClient("test-project", enable_mcp=False)
    client.client = MagicMock()
    mock_job = MagicMock()
    mock_job.result.return_value = []
    client.client.query.return_value = mock_job

    totals, categories = client.get_spending_snapshot("user123", "2026-08-01")
    assert totals == {"total_income": 0.0, "total_outflow": 0.0}
    assert categories == []
