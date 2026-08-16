"""Unit tests for Firestore Remote MCP toolset and client integration."""

from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from src.orchestrator.data.firestore_mcp import (
    DEFAULT_FIRESTORE_MCP_URL,
    create_firestore_mcp_toolset,
    get_firestore_auth_headers,
    get_firestore_mcp_toolset_from_registry,
    google_auth_header_provider,
    list_available_mcp_tools,
)


def test_get_firestore_auth_headers_valid_token():
    """Golden path: valid credentials return expected Authorization and Accept headers."""
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.token = "fake-access-token-12345"

    headers = get_firestore_auth_headers(credentials=mock_creds)
    assert headers["Authorization"] == "Bearer fake-access-token-12345"
    assert "application/json" in headers["Accept"]
    assert headers["Content-Type"] == "application/json"


def test_get_firestore_auth_headers_refreshes_invalid_token():
    """Error/edge path: invalid credentials trigger refresh."""
    mock_creds = MagicMock()
    mock_creds.valid = False
    mock_creds.token = "refreshed-token-999"

    headers = get_firestore_auth_headers(credentials=mock_creds)
    mock_creds.refresh.assert_called_once()
    assert headers["Authorization"] == "Bearer refreshed-token-999"


def test_get_firestore_auth_headers_no_token_raises_runtime_error():
    """Error path: missing token raises RuntimeError."""
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.token = None

    with pytest.raises(RuntimeError, match="Could not obtain valid access token"):
        get_firestore_auth_headers(credentials=mock_creds)


def test_get_firestore_auth_headers_default_credentials():
    """Golden path: uses google.auth.default when credentials argument is None."""
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.token = "default-creds-token"

    with patch("src.orchestrator.data.firestore_mcp.google_auth_default", return_value=(mock_creds, "test-proj")):
        headers = get_firestore_auth_headers()
        assert headers["Authorization"] == "Bearer default-creds-token"


@patch("google.adk.tools.mcp_tool.mcp_toolset.McpToolset")
def test_create_firestore_mcp_toolset(mock_mcp_toolset_cls):
    """Golden path: create_firestore_mcp_toolset initializes McpToolset with streamable HTTP."""
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.token = "test-token"

    toolset = create_firestore_mcp_toolset(credentials=mock_creds)

    mock_mcp_toolset_cls.assert_called_once()
    _, kwargs = mock_mcp_toolset_cls.call_args
    assert kwargs["connection_params"].url == DEFAULT_FIRESTORE_MCP_URL
    assert kwargs["tool_name_prefix"] == "firestore"
    assert callable(kwargs["header_provider"])

    # Test that header_provider function returns the dynamic headers
    provider_headers = kwargs["header_provider"](None)
    assert provider_headers["Authorization"] == "Bearer test-token"


@patch("google.adk.tools.mcp_tool.mcp_toolset.McpToolset")
def test_create_firestore_mcp_toolset_custom_url(mock_mcp_toolset_cls):
    """Parametrized custom URL override."""
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.token = "test-token"

    custom_url = "https://custom-firestore-proxy.internal/mcp"
    create_firestore_mcp_toolset(url=custom_url, credentials=mock_creds)

    mock_mcp_toolset_cls.assert_called_once()
    _, kwargs = mock_mcp_toolset_cls.call_args
    assert kwargs["connection_params"].url == custom_url


@patch("google.adk.integrations.agent_registry.AgentRegistry")
def test_get_firestore_mcp_toolset_from_registry_success(mock_registry_cls):
    """Golden path: AgentRegistry resolves registered MCP toolset."""
    mock_registry_instance = MagicMock()
    mock_registry_cls.return_value = mock_registry_instance
    mock_toolset = MagicMock()
    mock_registry_instance.get_mcp_toolset.return_value = mock_toolset

    result = get_firestore_mcp_toolset_from_registry(
        project_id="my-demo-project",
        location="us-central1",
    )

    mock_registry_cls.assert_called_once_with(
        project_id="my-demo-project",
        location="us-central1",
        header_provider=ANY,
    )
    mock_registry_instance.get_mcp_toolset.assert_called_once_with(
        mcp_server_name="projects/my-demo-project/locations/us-central1/mcpServers/firestore-mcp"
    )
    assert result == mock_toolset


@patch("src.orchestrator.data.firestore_mcp.create_firestore_mcp_toolset")
@patch("google.adk.integrations.agent_registry.AgentRegistry")
def test_get_firestore_mcp_toolset_from_registry_fallback_on_error(
    mock_registry_cls, mock_create_toolset
):
    """Error path: falls back to direct endpoint when registry raises an exception."""
    mock_registry_instance = MagicMock()
    mock_registry_cls.return_value = mock_registry_instance
    mock_registry_instance.get_mcp_toolset.side_effect = RuntimeError("Registry unreachable")

    mock_fallback_toolset = MagicMock()
    mock_create_toolset.return_value = mock_fallback_toolset

    mock_creds = MagicMock()
    result = get_firestore_mcp_toolset_from_registry(
        project_id="my-demo-project",
        location="global",
        credentials=mock_creds,
    )

    mock_create_toolset.assert_called_once_with(credentials=mock_creds)
    assert result == mock_fallback_toolset


def test_get_firestore_auth_headers_refresh_exception_handled():
    """Edge path: refresh exception logs warning and proceeds to check token."""
    mock_creds = MagicMock()
    mock_creds.valid = False
    mock_creds.token = "recovered-token"
    mock_creds.refresh.side_effect = Exception("Refresh failed")

    headers = get_firestore_auth_headers(credentials=mock_creds)
    assert headers["Authorization"] == "Bearer recovered-token"


def test_google_auth_header_provider():
    """Golden path: header provider calls get_firestore_auth_headers."""
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.token = "provider-test-token"
    with patch("src.orchestrator.data.firestore_mcp.google_auth_default", return_value=(mock_creds, "test-proj")):
        headers = google_auth_header_provider()
        assert headers["Authorization"] == "Bearer provider-test-token"


@patch("src.orchestrator.data.firestore_mcp.create_firestore_mcp_toolset")
@patch("src.orchestrator.data.firestore_mcp.google_auth_default", return_value=(MagicMock(), None))
def test_get_firestore_mcp_toolset_from_registry_no_project_falls_back(
    mock_auth_default, mock_create_toolset
):
    """Edge path: no project ID available in env or ADC falls back to direct toolset."""
    mock_create_toolset.return_value = MagicMock()
    with patch.dict("os.environ", {}, clear=True):
        toolset = get_firestore_mcp_toolset_from_registry(project_id=None)
        mock_create_toolset.assert_called_once()


@patch("src.orchestrator.data.firestore_mcp.create_firestore_mcp_toolset")
@patch("src.orchestrator.data.firestore_mcp.google_auth_default", return_value=(MagicMock(), "inferred-project"))
@patch("google.adk.integrations.agent_registry.AgentRegistry")
def test_get_firestore_mcp_toolset_from_registry_inferred_project(
    mock_registry_cls, mock_auth_default, mock_create_toolset
):
    """Golden path: project inferred from google_auth_default."""
    mock_registry_instance = MagicMock()
    mock_registry_cls.return_value = mock_registry_instance
    with patch.dict("os.environ", {}, clear=True):
        get_firestore_mcp_toolset_from_registry(project_id=None)
        mock_registry_cls.assert_called_once_with(
            project_id="inferred-project",
            location="global",
            header_provider=ANY,
        )



@patch("src.orchestrator.data.firestore_mcp.create_firestore_mcp_toolset")
@patch("src.orchestrator.data.firestore_mcp.google_auth_default", side_effect=Exception("ADC discovery failed"))
def test_get_firestore_mcp_toolset_from_registry_auth_exception_handled(
    mock_auth_default, mock_create_toolset
):
    """Edge path: google_auth_default exception handled gracefully and falls back."""
    mock_create_toolset.return_value = MagicMock()
    with patch.dict("os.environ", {}, clear=True):
        toolset = get_firestore_mcp_toolset_from_registry(project_id=None)
        mock_create_toolset.assert_called_once()


@pytest.mark.asyncio
async def test_list_available_mcp_tools():
    """Golden path: inspects exposed MCP tools from toolset."""
    mock_toolset = MagicMock()
    tool1 = MagicMock()
    tool1.name = "list_documents"
    tool2 = MagicMock()
    tool2.name = "get_document"

    mock_toolset.get_tools = AsyncMock(return_value=[tool1, tool2])

    tool_names = await list_available_mcp_tools(mock_toolset)
    assert tool_names == ["list_documents", "get_document"]


def test_value_conversions_roundtrip():
    from src.orchestrator.data.firestore_mcp import (
        dict_to_firestore_fields,
        firestore_doc_to_dict,
        firestore_value_to_python,
        python_to_firestore_value,
    )

    data = {
        "str_key": "hello",
        "int_key": 42,
        "float_key": 3.14,
        "bool_key": True,
        "false_key": False,
        "none_key": None,
        "list_key": ["a", 1, 2.5, True, None],
        "nested_dict": {"sub": "value", "count": 10},
    }

    fields = dict_to_firestore_fields(data)
    assert fields["str_key"] == {"stringValue": "hello"}
    assert fields["int_key"] == {"integerValue": "42"}
    assert fields["float_key"] == {"doubleValue": 3.14}
    assert fields["bool_key"] == {"booleanValue": True}
    assert fields["false_key"] == {"booleanValue": False}
    assert fields["none_key"] == {"nullValue": "NULL_VALUE"}
    assert "arrayValue" in fields["list_key"]
    assert "mapValue" in fields["nested_dict"]

    doc_obj = {"fields": fields}
    recovered = firestore_doc_to_dict(doc_obj)
    assert recovered == data

    # Test edge cases: empty map/array, timestamp, referenceValue
    assert firestore_value_to_python({"timestampValue": "2026-08-01T00:00:00Z"}) == "2026-08-01T00:00:00Z"
    assert firestore_value_to_python({"referenceValue": "projects/p/databases/(default)/documents/c/d"}) == "projects/p/databases/(default)/documents/c/d"
    assert firestore_value_to_python({"arrayValue": {}}) == []
    assert firestore_value_to_python({"mapValue": {}}) == {}
    assert firestore_value_to_python("not-a-dict") == "not-a-dict"


def test_firestore_mcp_client_get_document_success():
    from src.orchestrator.data.firestore_mcp import FirestoreMCPClient

    client = FirestoreMCPClient(project="test-proj")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {
            "structuredContent": {
                "fields": {
                    "user_id": {"stringValue": "u1"},
                    "total": {"integerValue": "500"},
                }
            }
        },
    }

    with (
        patch("src.orchestrator.data.firestore_mcp.get_firestore_auth_headers", return_value={"Authorization": "Bearer token"}),
        patch("httpx.Client.post", return_value=mock_resp),
    ):
        doc = client.get_document("holdings", "u1")
        assert doc == {"user_id": "u1", "total": 500}


def test_firestore_mcp_client_get_document_from_text_content():
    import json
    from src.orchestrator.data.firestore_mcp import FirestoreMCPClient

    client = FirestoreMCPClient(project="test-proj")
    raw_doc = {
        "fields": {
            "user_id": {"stringValue": "u2"},
            "score": {"doubleValue": 9.5},
        }
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {
            "content": [{"type": "text", "text": json.dumps(raw_doc)}]
        },
    }

    with (
        patch("src.orchestrator.data.firestore_mcp.get_firestore_auth_headers", return_value={"Authorization": "Bearer token"}),
        patch("httpx.Client.post", return_value=mock_resp),
    ):
        doc = client.get_document("holdings", "u2")
        assert doc == {"user_id": "u2", "score": 9.5}


def test_firestore_mcp_client_get_document_not_found():
    from src.orchestrator.data.firestore_mcp import FirestoreMCPClient

    client = FirestoreMCPClient(project="test-proj")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {
            "isError": True,
            "content": [{"type": "text", "text": "Document not found."}],
        },
    }

    with (
        patch("src.orchestrator.data.firestore_mcp.get_firestore_auth_headers", return_value={"Authorization": "Bearer token"}),
        patch("httpx.Client.post", return_value=mock_resp),
    ):
        assert client.get_document("holdings", "missing_user") is None


def test_firestore_mcp_client_call_tool_errors():
    from src.orchestrator.data.firestore_mcp import FirestoreMCPClient

    client = FirestoreMCPClient(project="test-proj")

    # JSON-RPC level error
    mock_err_resp = MagicMock()
    mock_err_resp.json.return_value = {"id": 1, "jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}}
    with (
        patch("src.orchestrator.data.firestore_mcp.get_firestore_auth_headers", return_value={"Authorization": "Bearer token"}),
        patch("httpx.Client.post", return_value=mock_err_resp),
    ):
        with pytest.raises(RuntimeError, match="MCP error"):
            client._call_tool("get_document", {})

    # Tool execution failure (isError=True)
    mock_tool_err_resp = MagicMock()
    mock_tool_err_resp.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {"isError": True, "content": [{"text": "Permission denied"}]},
    }
    with (
        patch("src.orchestrator.data.firestore_mcp.get_firestore_auth_headers", return_value={"Authorization": "Bearer token"}),
        patch("httpx.Client.post", return_value=mock_tool_err_resp),
    ):
        with pytest.raises(RuntimeError, match="MCP tool get_document failed"):
            client._call_tool("get_document", {})


def test_firestore_mcp_client_set_and_update_and_delete_document():
    from src.orchestrator.data.firestore_mcp import FirestoreMCPClient

    client = FirestoreMCPClient(project="test-proj")
    mock_ok_resp = MagicMock()
    mock_ok_resp.json.return_value = {"id": 1, "jsonrpc": "2.0", "result": {}}

    with (
        patch("src.orchestrator.data.firestore_mcp.get_firestore_auth_headers", return_value={"Authorization": "Bearer token"}),
        patch("httpx.Client.post", return_value=mock_ok_resp) as mock_post,
    ):
        client.set_document("holdings", "u1", {"cash": 100})
        assert mock_post.called

        # Test delete document
        client.delete_document("holdings", "u1")

    # Test update document merges with existing
    with (
        patch.object(client, "get_document", return_value={"cash": 100, "name": "Test"}),
        patch.object(client, "set_document") as mock_set,
    ):
        client.update_document("holdings", "u1", {"cash": 200})
        mock_set.assert_called_once_with("holdings", "u1", {"cash": 200, "name": "Test"})


def test_firestore_mcp_client_list_documents():
    import json
    from src.orchestrator.data.firestore_mcp import FirestoreMCPClient

    client = FirestoreMCPClient(project="test-proj")
    doc1 = {"fields": {"ips_id": {"stringValue": "ips1"}, "status": {"stringValue": "active"}}}
    doc2 = {"fields": {"ips_id": {"stringValue": "ips2"}, "status": {"stringValue": "superseded"}}}

    # StructuredContent
    mock_resp1 = MagicMock()
    mock_resp1.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {"structuredContent": {"documents": [doc1, doc2]}},
    }
    with (
        patch("src.orchestrator.data.firestore_mcp.get_firestore_auth_headers", return_value={"Authorization": "Bearer token"}),
        patch("httpx.Client.post", return_value=mock_resp1),
    ):
        docs = client.list_documents("ips")
        assert len(docs) == 2
        assert docs[0] == {"ips_id": "ips1", "status": "active"}

    # Text content
    mock_resp2 = MagicMock()
    mock_resp2.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {"content": [{"type": "text", "text": json.dumps({"documents": [doc1]})}]},
    }
    with (
        patch("src.orchestrator.data.firestore_mcp.get_firestore_auth_headers", return_value={"Authorization": "Bearer token"}),
        patch("httpx.Client.post", return_value=mock_resp2),
    ):
        docs = client.list_documents("ips")
        assert len(docs) == 1
        assert docs[0] == {"ips_id": "ips1", "status": "active"}

    # Not found returns empty list
    mock_err_resp = MagicMock()
    mock_err_resp.json.return_value = {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {"isError": True, "content": [{"text": "Collection not found"}]},
    }
    with (
        patch("src.orchestrator.data.firestore_mcp.get_firestore_auth_headers", return_value={"Authorization": "Bearer token"}),
        patch("httpx.Client.post", return_value=mock_err_resp),
    ):
        assert client.list_documents("missing_col") == []



