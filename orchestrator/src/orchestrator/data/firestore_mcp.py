"""Firestore Remote MCP Server toolset and client integration."""

import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from google.auth import default as google_auth_default
from google.auth.transport.requests import Request as GoogleAuthRequest

from ..logger import get_logger

if TYPE_CHECKING:
    from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

logger = get_logger(__name__)

DEFAULT_FIRESTORE_MCP_URL = "https://firestore.googleapis.com/mcp"
DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/datastore",
]


def get_firestore_auth_headers(credentials: Any = None) -> Dict[str, str]:
    """Generates authorization headers with a valid Google Cloud ADC token."""
    creds = credentials
    if creds is None:
        creds, _ = google_auth_default(scopes=DEFAULT_SCOPES)

    if not creds.valid:
        try:
            creds.refresh(GoogleAuthRequest())
        except Exception as e:
            logger.warning("Failed to refresh Google credentials for Firestore MCP: %s", e)

    token = getattr(creds, "token", None)
    if not token:
        raise RuntimeError("Could not obtain valid access token for Firestore Remote MCP.")

    return {
        "Accept": "text/event-stream, application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }


def create_firestore_mcp_toolset(
    url: str = DEFAULT_FIRESTORE_MCP_URL,
    credentials: Any = None,
) -> "McpToolset":
    """Constructs an ADK McpToolset connecting to the remote Firestore MCP endpoint."""
    from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StreamableHTTPConnectionParams

    connection_params = StreamableHTTPConnectionParams(url=url)

    def header_provider(context: Any = None) -> Dict[str, str]:
        return get_firestore_auth_headers(credentials=credentials)

    return McpToolset(
        connection_params=connection_params,
        header_provider=header_provider,
        tool_name_prefix="firestore",
    )


def google_auth_header_provider(context: Any = None) -> Dict[str, str]:
    """Header provider callback for AgentRegistry ADK integration."""
    return get_firestore_auth_headers()


def get_firestore_mcp_toolset_from_registry(
    project_id: Optional[str] = None,
    location: str = "global",
    credentials: Any = None,
) -> "McpToolset":
    """Discovers and constructs the Firestore McpToolset from Agent Registry with fallback."""
    proj = (
        project_id
        or os.environ.get("PROJECT_ID")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
    )
    if not proj:
        try:
            _, proj = google_auth_default(scopes=DEFAULT_SCOPES)
        except Exception:
            pass

    if proj:
        server_name = f"projects/{proj}/locations/{location}/mcpServers/firestore-mcp"
        try:
            from google.adk.integrations.agent_registry import AgentRegistry

            registry = AgentRegistry(
                project_id=proj,
                location=location,
                header_provider=google_auth_header_provider,
            )
            return registry.get_mcp_toolset(mcp_server_name=server_name)
        except Exception as e:
            logger.info(
                "Agent Registry lookup for %s failed (%s), falling back to direct endpoint",
                server_name,
                e,
            )

    return create_firestore_mcp_toolset(credentials=credentials)


async def list_available_mcp_tools(toolset: Any) -> List[str]:
    """Inspects and returns the names of all tools exposed by the MCP toolset."""
    tools = await toolset.get_tools()
    tool_names = []
    for t in tools:
        name = getattr(t, "name", str(t))
        tool_names.append(name)
    return tool_names
