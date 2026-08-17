"""Unit tests for BigQuery Remote MCP toolset and client integration."""

import json
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from src.orchestrator.data.bigquery_mcp import (
    DEFAULT_BIGQUERY_MCP_URL,
    BigQueryMCPClient,
    create_bigquery_mcp_toolset,
    get_bigquery_auth_headers,
    get_bigquery_mcp_toolset_from_registry,
    google_auth_header_provider,
    list_available_mcp_tools,
)


def test_get_bigquery_auth_headers_valid_token():
    """Golden path: valid credentials return expected Authorization and Accept headers."""
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.token = "fake-bq-access-token-12345"

    headers = get_bigquery_auth_headers(credentials=mock_creds)
    assert headers["Authorization"] == "Bearer fake-bq-access-token-12345"
    assert "application/json" in headers["Accept"]
    assert headers["Content-Type"] == "application/json"


def test_get_bigquery_auth_headers_refreshes_invalid_token():
    """Error/edge path: invalid credentials trigger refresh."""
    mock_creds = MagicMock()
    mock_creds.valid = False
    mock_creds.token = "refreshed-bq-token-999"

    headers = get_bigquery_auth_headers(credentials=mock_creds)
    mock_creds.refresh.assert_called_once()
    assert headers["Authorization"] == "Bearer refreshed-bq-token-999"


def test_get_bigquery_auth_headers_no_token_raises_runtime_error():
    """Error path: missing token raises RuntimeError."""
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.token = None

    with pytest.raises(RuntimeError, match="Could not obtain valid access token for BigQuery Remote MCP"):
        get_bigquery_auth_headers(credentials=mock_creds)


def test_get_bigquery_auth_headers_default_credentials():
    """Golden path: uses google.auth.default when credentials argument is None."""
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.token = "default-bq-creds-token"

    with patch("src.orchestrator.data.bigquery_mcp.google_auth_default", return_value=(mock_creds, "test-proj")):
        headers = get_bigquery_auth_headers()
        assert headers["Authorization"] == "Bearer default-bq-creds-token"


def test_get_bigquery_auth_headers_refresh_exception_handled():
    """Edge path: refresh exception logs warning and proceeds to check token."""
    mock_creds = MagicMock()
    mock_creds.valid = False
    mock_creds.token = "recovered-bq-token"
    mock_creds.refresh.side_effect = Exception("Refresh failed")

    headers = get_bigquery_auth_headers(credentials=mock_creds)
    assert headers["Authorization"] == "Bearer recovered-bq-token"


@patch("google.adk.tools.mcp_tool.mcp_toolset.McpToolset")
def test_create_bigquery_mcp_toolset(mock_mcp_toolset_cls):
    """Golden path: create_bigquery_mcp_toolset initializes McpToolset with streamable HTTP."""
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.token = "test-token"

    create_bigquery_mcp_toolset(credentials=mock_creds)

    mock_mcp_toolset_cls.assert_called_once()
    _, kwargs = mock_mcp_toolset_cls.call_args
    assert kwargs["connection_params"].url == DEFAULT_BIGQUERY_MCP_URL
    assert kwargs["tool_name_prefix"] == "bigquery"
    assert callable(kwargs["header_provider"])

    provider_headers = kwargs["header_provider"](None)
    assert provider_headers["Authorization"] == "Bearer test-token"


@patch("google.adk.tools.mcp_tool.mcp_toolset.McpToolset")
def test_create_bigquery_mcp_toolset_custom_url(mock_mcp_toolset_cls):
    """Parametrized custom URL override."""
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.token = "test-token"

    custom_url = "https://custom-bigquery-proxy.internal/mcp"
    create_bigquery_mcp_toolset(url=custom_url, credentials=mock_creds)

    mock_mcp_toolset_cls.assert_called_once()
    _, kwargs = mock_mcp_toolset_cls.call_args
    assert kwargs["connection_params"].url == custom_url


def test_google_auth_header_provider():
    """Golden path: header provider calls get_bigquery_auth_headers."""
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.token = "provider-test-bq-token"
    with patch("src.orchestrator.data.bigquery_mcp.google_auth_default", return_value=(mock_creds, "test-proj")):
        headers = google_auth_header_provider()
        assert headers["Authorization"] == "Bearer provider-test-bq-token"


@patch("google.adk.integrations.agent_registry.AgentRegistry")
def test_get_bigquery_mcp_toolset_from_registry_success(mock_registry_cls):
    """Golden path: AgentRegistry resolves registered MCP toolset."""
    mock_registry_instance = MagicMock()
    mock_registry_cls.return_value = mock_registry_instance
    mock_toolset = MagicMock()
    mock_registry_instance.get_mcp_toolset.return_value = mock_toolset

    result = get_bigquery_mcp_toolset_from_registry(
        project_id="my-demo-project",
        location="us-central1",
    )

    mock_registry_cls.assert_called_once_with(
        project_id="my-demo-project",
        location="us-central1",
        header_provider=ANY,
    )
    mock_registry_instance.get_mcp_toolset.assert_called_once_with(
        mcp_server_name="projects/my-demo-project/locations/us-central1/mcpServers/bigquery-mcp"
    )
    assert result == mock_toolset


@patch("src.orchestrator.data.bigquery_mcp.create_bigquery_mcp_toolset")
@patch("google.adk.integrations.agent_registry.AgentRegistry")
def test_get_bigquery_mcp_toolset_from_registry_fallback_on_error(mock_registry_cls, mock_create_toolset):
    """Error path: falls back to direct endpoint when registry raises an exception."""
    mock_registry_instance = MagicMock()
    mock_registry_cls.return_value = mock_registry_instance
    mock_registry_instance.get_mcp_toolset.side_effect = RuntimeError("Registry unreachable")

    mock_fallback_toolset = MagicMock()
    mock_create_toolset.return_value = mock_fallback_toolset

    mock_creds = MagicMock()
    result = get_bigquery_mcp_toolset_from_registry(
        project_id="my-demo-project",
        location="global",
        credentials=mock_creds,
    )

    mock_create_toolset.assert_called_once_with(credentials=mock_creds)
    assert result == mock_fallback_toolset


@patch("src.orchestrator.data.bigquery_mcp.create_bigquery_mcp_toolset")
@patch("src.orchestrator.data.bigquery_mcp.google_auth_default", return_value=(MagicMock(), None))
def test_get_bigquery_mcp_toolset_from_registry_no_project_falls_back(mock_auth_default, mock_create_toolset):
    """Edge path: no project ID available in env or ADC falls back to direct toolset."""
    mock_create_toolset.return_value = MagicMock()
    with patch.dict("os.environ", {}, clear=True):
        get_bigquery_mcp_toolset_from_registry(project_id=None)
        mock_create_toolset.assert_called_once()


@patch("src.orchestrator.data.bigquery_mcp.create_bigquery_mcp_toolset")
@patch("src.orchestrator.data.bigquery_mcp.google_auth_default", return_value=(MagicMock(), "inferred-project"))
@patch("google.adk.integrations.agent_registry.AgentRegistry")
def test_get_bigquery_mcp_toolset_from_registry_inferred_project(
    mock_registry_cls, mock_auth_default, mock_create_toolset
):
    """Golden path: project inferred from google_auth_default."""
    mock_registry_instance = MagicMock()
    mock_registry_cls.return_value = mock_registry_instance
    with patch.dict("os.environ", {}, clear=True):
        get_bigquery_mcp_toolset_from_registry(project_id=None)
        mock_registry_cls.assert_called_once_with(
            project_id="inferred-project",
            location="global",
            header_provider=ANY,
        )


@patch("src.orchestrator.data.bigquery_mcp.create_bigquery_mcp_toolset")
@patch("src.orchestrator.data.bigquery_mcp.google_auth_default", side_effect=Exception("ADC discovery failed"))
def test_get_bigquery_mcp_toolset_from_registry_auth_exception_handled(mock_auth_default, mock_create_toolset):
    """Edge path: google_auth_default exception handled gracefully and falls back."""
    mock_create_toolset.return_value = MagicMock()
    with patch.dict("os.environ", {}, clear=True):
        get_bigquery_mcp_toolset_from_registry(project_id=None)
        mock_create_toolset.assert_called_once()


@pytest.mark.asyncio
async def test_list_available_mcp_tools():
    """Golden path: inspects exposed BigQuery MCP tools from toolset."""
    mock_toolset = MagicMock()
    tool1 = MagicMock()
    tool1.name = "list_datasets"
    tool2 = MagicMock()
    tool2.name = "execute_query"

    mock_toolset.get_tools = AsyncMock(return_value=[tool1, tool2])

    tool_names = await list_available_mcp_tools(mock_toolset)
    assert tool_names == ["list_datasets", "execute_query"]


def test_bigquery_mcp_client_list_datasets_structured():
    """Golden path: list_datasets deserializes structuredContent datasets."""
    client = BigQueryMCPClient(project="test-proj")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {
            "structuredContent": {
                "datasets": [
                    {"datasetId": "portfolio_copilot"},
                    {"datasetId": "analytics"},
                ]
            }
        },
    }

    with (
        patch(
            "src.orchestrator.data.bigquery_mcp.get_bigquery_auth_headers",
            return_value={"Authorization": "Bearer token"},
        ),
        patch("httpx.Client.post", return_value=mock_resp),
    ):
        datasets = client.list_datasets()
        assert len(datasets) == 2
        assert datasets[0]["datasetId"] == "portfolio_copilot"


def test_bigquery_mcp_client_list_datasets_text_content_and_list_sc():
    """Edge path: list_datasets with text content and direct list structuredContent."""
    client = BigQueryMCPClient(project="test-proj")

    # Direct list structuredContent
    mock_resp1 = MagicMock()
    mock_resp1.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {"structuredContent": [{"datasetId": "d1"}]},
    }
    with (
        patch(
            "src.orchestrator.data.bigquery_mcp.get_bigquery_auth_headers",
            return_value={"Authorization": "Bearer token"},
        ),
        patch("httpx.Client.post", return_value=mock_resp1),
    ):
        assert client.list_datasets() == [{"datasetId": "d1"}]

    # Text content list
    mock_resp2 = MagicMock()
    mock_resp2.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {"content": [{"type": "text", "text": json.dumps([{"datasetId": "d2"}])}]},
    }
    with (
        patch(
            "src.orchestrator.data.bigquery_mcp.get_bigquery_auth_headers",
            return_value={"Authorization": "Bearer token"},
        ),
        patch("httpx.Client.post", return_value=mock_resp2),
    ):
        assert client.list_datasets() == [{"datasetId": "d2"}]

    # Text content dict
    mock_resp3 = MagicMock()
    mock_resp3.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {"content": [{"type": "text", "text": json.dumps({"datasets": [{"datasetId": "d3"}]})}]},
    }
    with (
        patch(
            "src.orchestrator.data.bigquery_mcp.get_bigquery_auth_headers",
            return_value={"Authorization": "Bearer token"},
        ),
        patch("httpx.Client.post", return_value=mock_resp3),
    ):
        assert client.list_datasets() == [{"datasetId": "d3"}]


def test_bigquery_mcp_client_list_datasets_not_found():
    """Error path: not found returns empty list."""
    client = BigQueryMCPClient(project="test-proj")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {
            "isError": True,
            "content": [{"type": "text", "text": "Project not found"}],
        },
    }
    with (
        patch(
            "src.orchestrator.data.bigquery_mcp.get_bigquery_auth_headers",
            return_value={"Authorization": "Bearer token"},
        ),
        patch("httpx.Client.post", return_value=mock_resp),
    ):
        assert client.list_datasets() == []


def test_bigquery_mcp_client_list_tables_success_and_not_found():
    """Golden and edge paths for list_tables."""
    client = BigQueryMCPClient(project="test-proj")

    # StructuredContent dict with tables
    mock_resp1 = MagicMock()
    mock_resp1.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {"structuredContent": {"tables": [{"tableId": "checking_transactions"}]}},
    }
    with (
        patch(
            "src.orchestrator.data.bigquery_mcp.get_bigquery_auth_headers",
            return_value={"Authorization": "Bearer token"},
        ),
        patch("httpx.Client.post", return_value=mock_resp1),
    ):
        tables = client.list_tables("portfolio_copilot")
        assert len(tables) == 1
        assert tables[0]["tableId"] == "checking_transactions"

    # StructuredContent list
    mock_resp2 = MagicMock()
    mock_resp2.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {"structuredContent": [{"tableId": "t2"}]},
    }
    with (
        patch(
            "src.orchestrator.data.bigquery_mcp.get_bigquery_auth_headers",
            return_value={"Authorization": "Bearer token"},
        ),
        patch("httpx.Client.post", return_value=mock_resp2),
    ):
        assert client.list_tables("portfolio_copilot") == [{"tableId": "t2"}]

    # Text content list and dict
    mock_resp3 = MagicMock()
    mock_resp3.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {"content": [{"type": "text", "text": json.dumps([{"tableId": "t3"}])}]},
    }
    with (
        patch(
            "src.orchestrator.data.bigquery_mcp.get_bigquery_auth_headers",
            return_value={"Authorization": "Bearer token"},
        ),
        patch("httpx.Client.post", return_value=mock_resp3),
    ):
        assert client.list_tables("portfolio_copilot") == [{"tableId": "t3"}]

    mock_resp4 = MagicMock()
    mock_resp4.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {"content": [{"type": "text", "text": json.dumps({"tables": [{"tableId": "t4"}]})}]},
    }
    with (
        patch(
            "src.orchestrator.data.bigquery_mcp.get_bigquery_auth_headers",
            return_value={"Authorization": "Bearer token"},
        ),
        patch("httpx.Client.post", return_value=mock_resp4),
    ):
        assert client.list_tables("portfolio_copilot") == [{"tableId": "t4"}]

    # Not found error
    mock_resp_err = MagicMock()
    mock_resp_err.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {"isError": True, "content": [{"text": "Dataset not found"}]},
    }
    with (
        patch(
            "src.orchestrator.data.bigquery_mcp.get_bigquery_auth_headers",
            return_value={"Authorization": "Bearer token"},
        ),
        patch("httpx.Client.post", return_value=mock_resp_err),
    ):
        assert client.list_tables("missing_ds") == []


def test_bigquery_mcp_client_get_table_schema():
    """Golden and edge paths for get_table_schema."""
    client = BigQueryMCPClient(project="test-proj")

    # StructuredContent dict
    mock_resp1 = MagicMock()
    mock_resp1.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {
            "structuredContent": {
                "fields": [
                    {"name": "user_id", "type": "STRING"},
                    {"name": "amount", "type": "NUMERIC"},
                ]
            }
        },
    }
    with (
        patch(
            "src.orchestrator.data.bigquery_mcp.get_bigquery_auth_headers",
            return_value={"Authorization": "Bearer token"},
        ),
        patch("httpx.Client.post", return_value=mock_resp1),
    ):
        schema = client.get_table_schema("portfolio_copilot", "checking_transactions")
        assert "fields" in schema
        assert len(schema["fields"]) == 2

    # Text content dict
    mock_resp2 = MagicMock()
    mock_resp2.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"fields": [{"name": "category", "type": "STRING"}]}),
                }
            ]
        },
    }
    with (
        patch(
            "src.orchestrator.data.bigquery_mcp.get_bigquery_auth_headers",
            return_value={"Authorization": "Bearer token"},
        ),
        patch("httpx.Client.post", return_value=mock_resp2),
    ):
        schema = client.get_table_schema("portfolio_copilot", "checking_transactions")
        assert "fields" in schema

    # Not found error
    mock_resp_err = MagicMock()
    mock_resp_err.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {"isError": True, "content": [{"text": "Table not found"}]},
    }
    with (
        patch(
            "src.orchestrator.data.bigquery_mcp.get_bigquery_auth_headers",
            return_value={"Authorization": "Bearer token"},
        ),
        patch("httpx.Client.post", return_value=mock_resp_err),
    ):
        assert client.get_table_schema("portfolio_copilot", "missing_table") == {}


def test_bigquery_mcp_client_execute_query():
    """Golden and edge paths for execute_query."""
    client = BigQueryMCPClient(project="test-proj")

    # StructuredContent list
    mock_resp1 = MagicMock()
    mock_resp1.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {"structuredContent": [{"total_spend": 120.50}]},
    }
    with (
        patch(
            "src.orchestrator.data.bigquery_mcp.get_bigquery_auth_headers",
            return_value={"Authorization": "Bearer token"},
        ),
        patch("httpx.Client.post", return_value=mock_resp1) as mock_post,
    ):
        rows = client.execute_query(
            "SELECT * FROM checking_transactions WHERE user_id = @user_id",
            query_parameters=[
                {"name": "user_id", "parameterType": {"type": "STRING"}, "parameterValue": {"value": "u1"}}
            ],
            maximum_bytes_billed=10485760,
        )
        assert rows == [{"total_spend": 120.50}]
        assert mock_post.called

    # StructuredContent dict with rows
    mock_resp2 = MagicMock()
    mock_resp2.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {"structuredContent": {"rows": [{"col": "val"}]}},
    }
    with (
        patch(
            "src.orchestrator.data.bigquery_mcp.get_bigquery_auth_headers",
            return_value={"Authorization": "Bearer token"},
        ),
        patch("httpx.Client.post", return_value=mock_resp2),
    ):
        assert client.execute_query("SELECT 1") == [{"col": "val"}]

    # Text content list
    mock_resp3 = MagicMock()
    mock_resp3.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {"content": [{"type": "text", "text": json.dumps([{"count": 5}])}]},
    }
    with (
        patch(
            "src.orchestrator.data.bigquery_mcp.get_bigquery_auth_headers",
            return_value={"Authorization": "Bearer token"},
        ),
        patch("httpx.Client.post", return_value=mock_resp3),
    ):
        assert client.execute_query("SELECT count(*)") == [{"count": 5}]

    # Text content dict with rows
    mock_resp4 = MagicMock()
    mock_resp4.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {"content": [{"type": "text", "text": json.dumps({"rows": [{"count": 10}]})}]},
    }
    with (
        patch(
            "src.orchestrator.data.bigquery_mcp.get_bigquery_auth_headers",
            return_value={"Authorization": "Bearer token"},
        ),
        patch("httpx.Client.post", return_value=mock_resp4),
    ):
        assert client.execute_query("SELECT count(*)") == [{"count": 10}]


def test_bigquery_mcp_client_explain_query():
    """Golden path for explain_query."""
    client = BigQueryMCPClient(project="test-proj")

    # StructuredContent dict
    mock_resp1 = MagicMock()
    mock_resp1.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {"structuredContent": {"totalBytesProcessed": "1048576", "statementType": "SELECT"}},
    }
    with (
        patch(
            "src.orchestrator.data.bigquery_mcp.get_bigquery_auth_headers",
            return_value={"Authorization": "Bearer token"},
        ),
        patch("httpx.Client.post", return_value=mock_resp1),
    ):
        plan = client.explain_query("SELECT 1")
        assert plan["totalBytesProcessed"] == "1048576"

    # Text content dict
    mock_resp2 = MagicMock()
    mock_resp2.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {"content": [{"type": "text", "text": json.dumps({"estimatedBytes": 500})}]},
    }
    with (
        patch(
            "src.orchestrator.data.bigquery_mcp.get_bigquery_auth_headers",
            return_value={"Authorization": "Bearer token"},
        ),
        patch("httpx.Client.post", return_value=mock_resp2),
    ):
        plan = client.explain_query("SELECT 1")
        assert plan["estimatedBytes"] == 500


def test_bigquery_mcp_client_call_tool_errors():
    """Error paths: JSON-RPC level errors and isError=True handling."""
    client = BigQueryMCPClient(project="test-proj")

    # JSON-RPC level error
    mock_err_resp = MagicMock()
    mock_err_resp.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "error": {"code": -32600, "message": "Invalid Request"},
    }
    with (
        patch(
            "src.orchestrator.data.bigquery_mcp.get_bigquery_auth_headers",
            return_value={"Authorization": "Bearer token"},
        ),
        patch("httpx.Client.post", return_value=mock_err_resp),
    ):
        with pytest.raises(RuntimeError, match="MCP error"):
            client._call_tool("execute_query", {})

    # Tool execution failure (isError=True)
    mock_tool_err_resp = MagicMock()
    mock_tool_err_resp.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {"isError": True, "content": [{"text": "Query execution failed: Syntax error"}]},
    }
    with (
        patch(
            "src.orchestrator.data.bigquery_mcp.get_bigquery_auth_headers",
            return_value={"Authorization": "Bearer token"},
        ),
        patch("httpx.Client.post", return_value=mock_tool_err_resp),
    ):
        with pytest.raises(RuntimeError, match="MCP tool execute_query failed: Query execution failed"):
            client._call_tool("execute_query", {})


def test_bigquery_mcp_client_tool_errors_and_invalid_json():
    """Edge paths: non-404 error raises RuntimeError and invalid json in content is handled."""
    client = BigQueryMCPClient(project="test-proj")

    # list_datasets generic error raises
    mock_err_resp = MagicMock()
    mock_err_resp.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {"isError": True, "content": [{"text": "Permission denied"}]},
    }
    with (
        patch(
            "src.orchestrator.data.bigquery_mcp.get_bigquery_auth_headers",
            return_value={"Authorization": "Bearer token"},
        ),
        patch("httpx.Client.post", return_value=mock_err_resp),
    ):
        with pytest.raises(RuntimeError, match="MCP tool list_dataset_ids failed: Permission denied"):
            client.list_datasets()

    # list_tables generic error raises
    with (
        patch(
            "src.orchestrator.data.bigquery_mcp.get_bigquery_auth_headers",
            return_value={"Authorization": "Bearer token"},
        ),
        patch("httpx.Client.post", return_value=mock_err_resp),
    ):
        with pytest.raises(RuntimeError, match="MCP tool list_table_ids failed: Permission denied"):
            client.list_tables("dataset1")

    # get_table_schema generic error raises
    with (
        patch(
            "src.orchestrator.data.bigquery_mcp.get_bigquery_auth_headers",
            return_value={"Authorization": "Bearer token"},
        ),
        patch("httpx.Client.post", return_value=mock_err_resp),
    ):
        with pytest.raises(RuntimeError, match="MCP tool get_table_info failed: Permission denied"):
            client.get_table_schema("dataset1", "table1")

    # Invalid JSON in content text
    mock_invalid_json_resp = MagicMock()
    mock_invalid_json_resp.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {"content": [{"type": "text", "text": "not valid json {{"}]},
    }
    with (
        patch(
            "src.orchestrator.data.bigquery_mcp.get_bigquery_auth_headers",
            return_value={"Authorization": "Bearer token"},
        ),
        patch("httpx.Client.post", return_value=mock_invalid_json_resp),
    ):
        assert client.list_datasets() == []
        assert client.list_tables("dataset1") == []
        assert client.get_table_schema("dataset1", "table1") == {}
        assert client.execute_query("SELECT 1") == []
        assert client.explain_query("SELECT 1") == {}


def test_decode_bigquery_mcp_rows_rest_format():
    """Golden path: decodes BigQuery REST-format schema and rows into dicts with appropriate types."""
    from src.orchestrator.data.bigquery_mcp import _decode_bigquery_mcp_rows

    data = {
        "schema": {
            "fields": [
                {"name": "user_id", "type": "STRING"},
                {"name": "count", "type": "INTEGER"},
                {"name": "amount", "type": "FLOAT"},
                {"name": "active", "type": "BOOLEAN"},
            ]
        },
        "rows": [
            {"f": [{"v": "usr_1"}, {"v": "42"}, {"v": "-120.50"}, {"v": "true"}]},
            {"f": [{"v": "usr_2"}, {"v": None}, {"v": "0.0"}, {"v": "false"}]},
        ],
    }

    decoded = _decode_bigquery_mcp_rows(data)
    assert len(decoded) == 2
    assert decoded[0] == {"user_id": "usr_1", "count": 42, "amount": -120.50, "active": True}
    assert decoded[1] == {"user_id": "usr_2", "count": None, "amount": 0.0, "active": False}


def test_decode_bigquery_mcp_rows_empty_and_passthrough():
    """Edge path: empty rows and direct dict passthrough."""
    from src.orchestrator.data.bigquery_mcp import _decode_bigquery_mcp_rows

    assert _decode_bigquery_mcp_rows({}) == []
    assert _decode_bigquery_mcp_rows({"rows": []}) == []

    # Direct dict passthrough
    mock_rows = [{"user_id": "u1", "amount": 10.0}]
    assert _decode_bigquery_mcp_rows({"rows": mock_rows}) == mock_rows
