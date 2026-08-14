"""Unit tests for Firestore Remote MCP toolset and client integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.orchestrator.data.firestore_mcp import (
    DEFAULT_FIRESTORE_MCP_URL,
    create_firestore_mcp_toolset,
    get_firestore_auth_headers,
    get_firestore_mcp_toolset_from_registry,
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


@patch("src.orchestrator.data.firestore_mcp.McpToolset")
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


@patch("src.orchestrator.data.firestore_mcp.McpToolset")
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


@patch("src.orchestrator.data.firestore_mcp.AgentRegistry")
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
    )
    mock_registry_instance.get_mcp_toolset.assert_called_once_with(
        mcp_server_name="projects/my-demo-project/locations/us-central1/mcpServers/firestore-mcp"
    )
    assert result == mock_toolset


@patch("src.orchestrator.data.firestore_mcp.create_firestore_mcp_toolset")
@patch("src.orchestrator.data.firestore_mcp.AgentRegistry")
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
@patch("src.orchestrator.data.firestore_mcp.AgentRegistry")
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


