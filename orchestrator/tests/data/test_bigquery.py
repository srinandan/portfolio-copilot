import pytest
from orchestrator.data.bigquery import BigQueryClient
from unittest.mock import patch, MagicMock

@patch('google.cloud.bigquery.Client')
def test_validate_and_execute_nl_sql_valid_query(mock_client):
    client = BigQueryClient("test-project")

    # Mocking bigquery.Client
    client.client = MagicMock()
    mock_job = MagicMock()
    mock_job.result.return_value = [{"col": 1}]
    client.client.query.return_value = mock_job

    # Should not raise an exception
    result = client.validate_and_execute_nl_sql("user123", "SELECT * FROM chase_transactions WHERE user_id = @user_id")
    assert result == [{"col": 1}]

@pytest.mark.parametrize("query, error_msg", [
    ("UPDATE chase_transactions SET amount = 0 WHERE user_id = @user_id", "Write-intent SQL refused"),
    ("DELETE FROM chase_transactions WHERE user_id = @user_id", "Write-intent SQL refused"),
    ("SELECT * FROM some_other_table WHERE user_id = @user_id", "must target the chase_transactions table"),
    ("SELECT * FROM chase_transactions WHERE amount > 0", "must include @user_id parameter"),
])
@patch('google.cloud.bigquery.Client')
def test_validate_and_execute_nl_sql_invalid_queries(mock_client, query, error_msg):
    client = BigQueryClient("test-project")

    with pytest.raises(ValueError) as excinfo:
         client.validate_and_execute_nl_sql("user123", query)

    assert error_msg in str(excinfo.value)
