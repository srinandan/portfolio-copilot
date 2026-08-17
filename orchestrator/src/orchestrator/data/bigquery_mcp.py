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


def _decode_bigquery_mcp_rows(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Decodes BigQuery REST-format rows (f: [{v: ...}]) into a list of column-name-keyed dicts."""
    schema_fields = data.get("schema", {}).get("fields", [])
    raw_rows = data.get("rows", [])
    if not raw_rows:
        return []

    # If raw_rows is already list of dicts with normal keys (e.g. from mock), return as is
    if isinstance(raw_rows[0], dict) and "f" not in raw_rows[0]:
        return raw_rows

    col_names = [f.get("name", f"col_{i}") for i, f in enumerate(schema_fields)]
    col_types = [f.get("type", "STRING").upper() for f in schema_fields]

    decoded = []
    for r in raw_rows:
        row_dict: Dict[str, Any] = {}
        f_list = r.get("f", []) if isinstance(r, dict) else []
        for i, col in enumerate(col_names):
            if i < len(f_list):
                val = f_list[i].get("v") if isinstance(f_list[i], dict) else f_list[i]
                if val is not None and i < len(col_types):
                    ctype = col_types[i]
                    if ctype in ("INTEGER", "INT64"):
                        try:
                            val = int(val)
                        except (ValueError, TypeError):
                            pass
                    elif ctype in ("FLOAT", "FLOAT64", "NUMERIC", "BIGNUMERIC"):
                        try:
                            val = float(val)
                        except (ValueError, TypeError):
                            pass
                    elif ctype in ("BOOLEAN", "BOOL"):
                        val = str(val).lower() == "true"
                row_dict[col] = val
        decoded.append(row_dict)
    return decoded


class BigQueryMCPClient:
    """Synchronous HTTP client for BigQuery Remote Model Context Protocol (MCP) Server.

    Executes JSON-RPC 2.0 tool calls (list_dataset_ids, list_table_ids, get_table_info,
    execute_sql_readonly) over Streamable HTTP against https://bigquery.googleapis.com/mcp.
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
        result = self._call_tool("list_dataset_ids", {"projectId": target_project}, check_error=False)
        if result.get("isError"):
            content = result.get("content", [])
            err_msg = (
                content[0].get("text", "") if content and isinstance(content, list) and "text" in content[0] else ""
            )
            if "not found" in err_msg.lower():
                return []
            raise RuntimeError(f"MCP tool list_dataset_ids failed: {err_msg}")

        datasets = []
        if "structuredContent" in result:
            sc = result["structuredContent"]
            if isinstance(sc, list):
                datasets = sc
            elif isinstance(sc, dict) and "datasets" in sc:
                datasets = sc["datasets"]
        else:
            content = result.get("content", [])
            if content and isinstance(content, list) and "text" in content[0]:
                try:
                    parsed = json.loads(content[0]["text"])
                    if isinstance(parsed, list):
                        datasets = parsed
                    elif isinstance(parsed, dict) and "datasets" in parsed:
                        datasets = parsed["datasets"]
                except Exception:
                    pass

        normalized = []
        for d in datasets:
            if isinstance(d, dict):
                d_id = d.get("id", "")
                dataset_name = d_id.split(":")[-1] if ":" in d_id else d_id
                item = dict(d)
                item["datasetId"] = item.get("datasetId") or dataset_name
                normalized.append(item)
            elif isinstance(d, str):
                normalized.append({"datasetId": d, "id": d})
        return normalized

    def list_tables(self, dataset_id: str, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists tables in a specified BigQuery dataset."""
        target_project = project_id or self.project
        result = self._call_tool(
            "list_table_ids",
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
            raise RuntimeError(f"MCP tool list_table_ids failed: {err_msg}")

        tables = []
        if "structuredContent" in result:
            sc = result["structuredContent"]
            if isinstance(sc, list):
                tables = sc
            elif isinstance(sc, dict) and "tables" in sc:
                tables = sc["tables"]
        else:
            content = result.get("content", [])
            if content and isinstance(content, list) and "text" in content[0]:
                try:
                    parsed = json.loads(content[0]["text"])
                    if isinstance(parsed, list):
                        tables = parsed
                    elif isinstance(parsed, dict) and "tables" in parsed:
                        tables = parsed["tables"]
                except Exception:
                    pass

        normalized = []
        for t in tables:
            if isinstance(t, dict):
                t_id = t.get("id", "")
                table_name = t_id.split(".")[-1] if "." in t_id else t_id
                item = dict(t)
                item["tableId"] = item.get("tableId") or table_name
                normalized.append(item)
            elif isinstance(t, str):
                normalized.append({"tableId": t, "id": t})
        return normalized

    def get_table_schema(self, dataset_id: str, table_id: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Fetches schema information (columns, types, descriptions) for a table."""
        target_project = project_id or self.project
        result = self._call_tool(
            "get_table_info",
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
            raise RuntimeError(f"MCP tool get_table_info failed: {err_msg}")

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
        import re

        target_project = project_id or self.project
        resolved_query = query
        if query_parameters:
            for p in query_parameters:
                p_name = p.get("name")
                p_val = p.get("parameterValue", {}).get("value")
                if p_name and p_val is not None:
                    p_type = p.get("parameterType", {}).get("type", "STRING")
                    if p_type == "STRING":
                        resolved_query = re.sub(rf"@{p_name}\b", f"'{p_val}'", resolved_query)
                    else:
                        resolved_query = re.sub(rf"@{p_name}\b", str(p_val), resolved_query)

        args: Dict[str, Any] = {
            "query": resolved_query,
            "projectId": target_project,
        }

        result = self._call_tool("execute_sql_readonly", args, check_error=True)

        payload_dict = None
        if "structuredContent" in result:
            sc = result["structuredContent"]
            if isinstance(sc, list):
                return sc
            if isinstance(sc, dict):
                payload_dict = sc

        if payload_dict is None:
            content = result.get("content", [])
            if content and isinstance(content, list) and "text" in content[0]:
                try:
                    parsed = json.loads(content[0]["text"])
                    if isinstance(parsed, list):
                        return parsed
                    if isinstance(parsed, dict):
                        payload_dict = parsed
                except Exception:
                    pass

        if payload_dict is not None:
            return _decode_bigquery_mcp_rows(payload_dict)

        return []

    def explain_query(self, query: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Validates query syntax and returns execution plan / cost estimate."""
        target_project = project_id or self.project
        result = self._call_tool(
            "execute_sql_readonly",
            {"query": query, "projectId": target_project, "dryRun": True},
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
