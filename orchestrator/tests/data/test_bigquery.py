from unittest.mock import MagicMock, patch

import pytest

from src.orchestrator.data.bigquery import BigQueryClient, prepare_secure_sql


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
    call_kwargs = mock_mcp.execute_query.call_args[1]
    assert "WITH checking_transactions AS" in call_kwargs["query"]
    assert "@user_id" in call_kwargs["query"]


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
    call_args = client.client.query.call_args[0]
    assert "WITH checking_transactions AS" in call_args[0]


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
    call_args = client.client.query.call_args[0]
    assert "WITH checking_transactions AS" in call_args[0]


@pytest.mark.parametrize(
    "query, error_msg",
    [
        ("", "Query cannot be empty"),
        ("UPDATE checking_transactions SET amount = 0 WHERE user_id = @user_id", "Read-only queries only"),
        ("DELETE FROM checking_transactions WHERE user_id = @user_id", "Read-only queries only"),
        ("DROP TABLE checking_transactions", "Read-only queries only"),
        ("INSERT INTO checking_transactions VALUES (1)", "Read-only queries only"),
        ("SELECT * FROM (UPDATE checking_transactions)", "Write-intent SQL refused: UPDATE"),
        ("SELECT * FROM (DELETE FROM checking_transactions)", "Write-intent SQL refused: DELETE"),
        ("SELECT * FROM (MERGE checking_transactions)", "Write-intent SQL refused: MERGE"),
        ("SELECT * FROM checking_transactions; SELECT * FROM other", "Multi-statement queries are not permitted"),
        ("SELECT * FROM some_other_table WHERE user_id = @user_id", "must target a transactions table"),
        ("SELECT * FROM INFORMATION_SCHEMA.TABLES JOIN checking_transactions", "INFORMATION_SCHEMA"),
    ],
)
@patch("google.cloud.bigquery.Client")
def test_validate_and_execute_nl_sql_invalid_queries(mock_client, query, error_msg):
    client = BigQueryClient("test-project")

    with pytest.raises(ValueError) as excinfo:
        client.validate_and_execute_nl_sql("user123", query)

    assert error_msg in str(excinfo.value)


def test_prepare_secure_sql_wrapping_and_scoping():
    sql = "SELECT * FROM `custom-proj.portfolio_copilot.checking_transactions` WHERE amount > 100"
    secure_sql, params = prepare_secure_sql(sql, "user_xyz", "custom-proj")

    assert "WITH checking_transactions AS (" in secure_sql
    assert "SELECT * FROM `custom-proj.portfolio_copilot.checking_transactions` WHERE user_id = @user_id" in secure_sql
    assert "SELECT * FROM checking_transactions WHERE amount > 100 LIMIT 100" in secure_sql
    assert params == [{"name": "user_id", "parameterType": {"type": "STRING"}, "parameterValue": {"value": "user_xyz"}}]


def test_prepare_secure_sql_preserves_existing_limit():
    sql = "SELECT normalized_category, sum(amount) FROM checking_transactions GROUP BY 1 LIMIT 10;"
    secure_sql, _ = prepare_secure_sql(sql, "user_xyz", "proj")
    assert secure_sql.endswith("LIMIT 10;")
    assert "LIMIT 100" not in secure_sql


def test_prepare_secure_sql_strips_comments():
    sql = "/* leading comment */ SELECT * FROM checking_transactions -- trailing comment"
    secure_sql, _ = prepare_secure_sql(sql, "user_xyz", "proj")
    assert "leading comment" not in secure_sql
    assert "trailing comment" not in secure_sql
    assert "LIMIT 100" in secure_sql


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


@patch("google.cloud.bigquery.Client")
def test_get_spending_snapshot_mcp_path_and_fallback(mock_client_cls):
    client = BigQueryClient("test-project", enable_mcp=True)
    mock_mcp = MagicMock()
    mock_mcp.execute_query.return_value = [
        {
            "total_income": 12000.0,
            "total_outflow": 5000.0,
            "category_totals": [
                {"normalized_category": "groceries", "current_month_spend": 400.0, "trailing_3mo_avg": 350.0}
            ],
        }
    ]
    client._mcp_client = mock_mcp

    totals, categories = client.get_spending_snapshot("user123", "2026-08-01")
    assert totals == {"total_income": 12000.0, "total_outflow": 5000.0}
    assert len(categories) == 1
    assert categories[0]["normalized_category"] == "groceries"

    # MCP empty results
    mock_mcp.execute_query.return_value = []
    totals, categories = client.get_spending_snapshot("user123", "2026-08-01")
    assert totals == {"total_income": 0.0, "total_outflow": 0.0}
    assert categories == []

    # MCP failure falls back to direct
    mock_mcp.execute_query.side_effect = RuntimeError("MCP query timeout")
    client.client = MagicMock()
    mock_job = MagicMock()
    mock_row = MagicMock()
    mock_row.total_income = 8000.0
    mock_row.total_outflow = 3000.0
    mock_row.category_totals = []
    mock_job.result.return_value = [mock_row]
    client.client.query.return_value = mock_job

    totals, categories = client.get_spending_snapshot("user123", "2026-08-01")
    assert totals == {"total_income": 8000.0, "total_outflow": 3000.0}


@patch("google.cloud.bigquery.Client")
def test_get_monthly_spending_totals_mcp_path_and_fallback(mock_client_cls):
    client = BigQueryClient("test-project", enable_mcp=True)
    mock_mcp = MagicMock()
    mock_mcp.execute_query.return_value = [{"normalized_category": "housing", "current_month_spend": 2000.0}]
    client._mcp_client = mock_mcp

    rows = client.get_monthly_spending_totals("user123", "2026-08-01")
    assert len(rows) == 1
    assert rows[0]["normalized_category"] == "housing"

    # Fallback on error
    mock_mcp.execute_query.side_effect = RuntimeError("MCP error")
    client.client = MagicMock()
    mock_job = MagicMock()
    mock_job.result.return_value = [{"normalized_category": "utilities", "current_month_spend": 150.0}]
    client.client.query.return_value = mock_job

    rows = client.get_monthly_spending_totals("user123", "2026-08-01")
    assert len(rows) == 1
    assert rows[0]["normalized_category"] == "utilities"


@patch("google.cloud.bigquery.Client")
def test_get_trailing_income_and_outflow_mcp_path_and_fallback(mock_client_cls):
    client = BigQueryClient("test-project", enable_mcp=True)
    mock_mcp = MagicMock()
    mock_mcp.execute_query.return_value = [{"total_income": 9000.0, "total_outflow": 4500.0}]
    client._mcp_client = mock_mcp

    res = client.get_trailing_income_and_outflow("user123", "2026-08-01")
    assert res == {"total_income": 9000.0, "total_outflow": 4500.0}

    # Empty result from MCP
    mock_mcp.execute_query.return_value = []
    res = client.get_trailing_income_and_outflow("user123", "2026-08-01")
    assert res == {"total_income": 0.0, "total_outflow": 0.0}

    # Fallback on error
    mock_mcp.execute_query.side_effect = RuntimeError("MCP error")
    client.client = MagicMock()
    mock_job = MagicMock()
    mock_row = MagicMock()
    mock_row.total_income = 7000.0
    mock_row.total_outflow = 3500.0
    mock_job.result.return_value = [mock_row]
    client.client.query.return_value = mock_job

    res = client.get_trailing_income_and_outflow("user123", "2026-08-01")
    assert res == {"total_income": 7000.0, "total_outflow": 3500.0}
