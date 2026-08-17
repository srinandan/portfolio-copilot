"""BigQuery Remote MCP Server toolset and client integration."""

import json
import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import httpx
from google.auth import default as google_auth_default
from google.auth.transport.requests import Request as GoogleAuthRequest

from ..logger import get_logger

if TYPE_CHECKING:
    from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

logger = get_logger(__name__)

DEFAULT_BIGQUERY_MCP_URL = "https://bigquery.googleapis.com/mcp"
DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/bigquery",
    "https://www.googleapis.com/auth/bigquery.readonly",
]


def get_bigquery_auth_headers(credentials: Any = None) -> Dict[str, str]:
    """Generates authorization headers with a valid Google Cloud ADC token for BigQuery Remote MCP."""
    creds = credentials
    if creds is None:
        creds, _ = google_auth_default(scopes=DEFAULT_SCOPES)

    if not creds.valid:
        try:
            creds.refresh(GoogleAuthRequest())
        except Exception as e:
            logger.warning("Failed to refresh Google credentials for BigQuery MCP: %s", e)

    token = getattr(creds, "token", None)
    if not token:
        raise RuntimeError("Could not obtain valid access token for BigQuery Remote MCP.")

    return {
        "Accept": "text/event-stream, application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }


def create_bigquery_mcp_toolset(
    url: str = DEFAULT_BIGQUERY_MCP_URL,
    credentials: Any = None,
) -> "McpToolset":
    """Constructs an ADK McpToolset connecting to the remote BigQuery MCP endpoint."""
    from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StreamableHTTPConnectionParams

    connection_params = StreamableHTTPConnectionParams(url=url)

    def header_provider(context: Any = None) -> Dict[str, str]:
        return get_bigquery_auth_headers(credentials=credentials)

    return McpToolset(
        connection_params=connection_params,
        header_provider=header_provider,
        tool_name_prefix="bigquery",
    )


def google_auth_header_provider(context: Any = None) -> Dict[str, str]:
    """Header provider callback for AgentRegistry ADK integration."""
    return get_bigquery_auth_headers()


def get_bigquery_mcp_toolset_from_registry(
    project_id: Optional[str] = None,
    location: str = "global",
    credentials: Any = None,
) -> "McpToolset":
    """Discovers and constructs the BigQuery McpToolset from Agent Registry with fallback."""
    proj = project_id or os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not proj:
        try:
            _, proj = google_auth_default(scopes=DEFAULT_SCOPES)
        except Exception:
            pass

    if proj:
        server_name = f"projects/{proj}/locations/{location}/mcpServers/bigquery-mcp"
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

    return create_bigquery_mcp_toolset(credentials=credentials)


async def list_available_mcp_tools(toolset: Any) -> List[str]:
    """Inspects and returns the names of all tools exposed by the MCP toolset."""
    tools = await toolset.get_tools()
    tool_names = []
    for t in tools:
        name = getattr(t, "name", str(t))
        tool_names.append(name)
    return tool_names


class BigQueryMCPClient:
    """Synchronous HTTP client for BigQuery Remote Model Context Protocol (MCP) Server.

    Executes JSON-RPC 2.0 tool calls (list_datasets, list_tables, get_table_schema,
    execute_query, explain_query) over Streamable HTTP against https://bigquery.googleapis.com/mcp.
    """

    def __init__(
        self,
        project: Optional[str] = None,
        url: str = DEFAULT_BIGQUERY_MCP_URL,
        credentials: Any = None,
        timeout: float = 15.0,
    ):
        self.project = (
            project or os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT") or "test-project"
        )
        self.url = url
        self.credentials = credentials
        self.timeout = timeout

    def _call_tool(self, tool_name: str, arguments: Dict[str, Any], check_error: bool = True) -> Dict[str, Any]:
        """Calls a tool on the BigQuery Remote MCP Server via JSON-RPC 2.0."""
        from opentelemetry import trace as ot_trace

        headers = get_bigquery_auth_headers(credentials=self.credentials)
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }
        tracer = ot_trace.get_tracer("orchestrator.data.bigquery_mcp")
        with tracer.start_as_current_span(
            f"bigquery.mcp.{tool_name}",
            attributes={
                "db.system": "bigquery",
                "mcp.tool": tool_name,
                "mcp.server": "bigquery-mcp",
                "net.peer.name": "bigquery.googleapis.com",
            },
        ):
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(self.url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                if "error" in data:
                    raise RuntimeError(f"MCP error: {data['error']}")
                result = data.get("result", {})
                if check_error and result.get("isError"):
                    err_msg = ""
                    content = result.get("content", [])
                    if content and isinstance(content, list) and "text" in content[0]:
                        err_msg = content[0]["text"]
                    raise RuntimeError(f"MCP tool {tool_name} failed: {err_msg}")
                return result

    def list_datasets(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists BigQuery datasets in the GCP project."""
        target_project = project_id or self.project
        result = self._call_tool("list_datasets", {"projectId": target_project}, check_error=False)
        if result.get("isError"):
            content = result.get("content", [])
            err_msg = (
                content[0].get("text", "") if content and isinstance(content, list) and "text" in content[0] else ""
            )
            if "not found" in err_msg.lower():
                return []
            raise RuntimeError(f"MCP tool list_datasets failed: {err_msg}")

        if "structuredContent" in result:
            sc = result["structuredContent"]
            if isinstance(sc, list):
                return sc
            if isinstance(sc, dict) and "datasets" in sc:
                return sc["datasets"]

        content = result.get("content", [])
        if content and isinstance(content, list) and "text" in content[0]:
            try:
                parsed = json.loads(content[0]["text"])
                if isinstance(parsed, list):
                    return parsed
                if isinstance(parsed, dict) and "datasets" in parsed:
                    return parsed["datasets"]
            except Exception:
                pass
        return []

    def list_tables(self, dataset_id: str, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists tables in a specified BigQuery dataset."""
        target_project = project_id or self.project
        result = self._call_tool(
            "list_tables",
            {"projectId": target_project, "datasetId": dataset_id},
            check_error=False,
        )
        if result.get("isError"):
            content = result.get("content", [])
            err_msg = (
                content[0].get("text", "") if content and isinstance(content, list) and "text" in content[0] else ""
            )
            if "not found" in err_msg.lower():
                return []
            raise RuntimeError(f"MCP tool list_tables failed: {err_msg}")

        if "structuredContent" in result:
            sc = result["structuredContent"]
            if isinstance(sc, list):
                return sc
            if isinstance(sc, dict) and "tables" in sc:
                return sc["tables"]

        content = result.get("content", [])
        if content and isinstance(content, list) and "text" in content[0]:
            try:
                parsed = json.loads(content[0]["text"])
                if isinstance(parsed, list):
                    return parsed
                if isinstance(parsed, dict) and "tables" in parsed:
                    return parsed["tables"]
            except Exception:
                pass
        return []

    def get_table_schema(self, dataset_id: str, table_id: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Fetches schema information (columns, types, descriptions) for a table."""
        target_project = project_id or self.project
        result = self._call_tool(
            "get_table_schema",
            {"projectId": target_project, "datasetId": dataset_id, "tableId": table_id},
            check_error=False,
        )
        if result.get("isError"):
            content = result.get("content", [])
            err_msg = (
                content[0].get("text", "") if content and isinstance(content, list) and "text" in content[0] else ""
            )
            if "not found" in err_msg.lower():
                return {}
            raise RuntimeError(f"MCP tool get_table_schema failed: {err_msg}")

        if "structuredContent" in result:
            sc = result["structuredContent"]
            if isinstance(sc, dict):
                return sc

        content = result.get("content", [])
        if content and isinstance(content, list) and "text" in content[0]:
            try:
                parsed = json.loads(content[0]["text"])
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
        return {}

    def execute_query(
        self,
        query: str,
        project_id: Optional[str] = None,
        query_parameters: Optional[List[Dict[str, Any]]] = None,
        maximum_bytes_billed: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Executes a read-only SQL query via BigQuery Remote MCP Server."""
        target_project = project_id or self.project
        args: Dict[str, Any] = {
            "query": query,
            "projectId": target_project,
        }
        if query_parameters is not None:
            args["queryParameters"] = query_parameters
        if maximum_bytes_billed is not None:
            args["maximumBytesBilled"] = str(maximum_bytes_billed)

        result = self._call_tool("execute_query", args, check_error=True)

        if "structuredContent" in result:
            sc = result["structuredContent"]
            if isinstance(sc, list):
                return sc
            if isinstance(sc, dict) and "rows" in sc:
                return sc["rows"]

        content = result.get("content", [])
        if content and isinstance(content, list) and "text" in content[0]:
            try:
                parsed = json.loads(content[0]["text"])
                if isinstance(parsed, list):
                    return parsed
                if isinstance(parsed, dict) and "rows" in parsed:
                    return parsed["rows"]
            except Exception:
                pass
        return []

    def explain_query(self, query: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Validates query syntax and returns execution plan / cost estimate."""
        target_project = project_id or self.project
        result = self._call_tool(
            "explain_query",
            {"query": query, "projectId": target_project},
            check_error=True,
        )

        if "structuredContent" in result and isinstance(result["structuredContent"], dict):
            return result["structuredContent"]

        content = result.get("content", [])
        if content and isinstance(content, list) and "text" in content[0]:
            try:
                parsed = json.loads(content[0]["text"])
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
        return {}
