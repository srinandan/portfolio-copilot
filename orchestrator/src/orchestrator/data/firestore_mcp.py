"""Firestore Remote MCP Server toolset and client integration."""

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
    proj = project_id or os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
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


def python_to_firestore_value(val: Any) -> Dict[str, Any]:
    """Converts a Python primitive/dict/list into a Firestore Typed Value map."""
    if val is None:
        return {"nullValue": "NULL_VALUE"}
    if isinstance(val, bool):
        return {"booleanValue": val}
    if isinstance(val, int):
        return {"integerValue": str(val)}
    if isinstance(val, float):
        return {"doubleValue": val}
    if isinstance(val, str):
        return {"stringValue": val}
    if isinstance(val, (list, tuple)):
        return {"arrayValue": {"values": [python_to_firestore_value(v) for v in val]}}
    if isinstance(val, dict):
        return {"mapValue": {"fields": {k: python_to_firestore_value(v) for k, v in val.items()}}}
    return {"stringValue": str(val)}


def firestore_value_to_python(val_obj: Any) -> Any:
    """Converts a Firestore Typed Value map into a Python primitive/dict/list."""
    if not isinstance(val_obj, dict):
        return val_obj
    if "stringValue" in val_obj:
        return val_obj["stringValue"]
    if "integerValue" in val_obj:
        return int(val_obj["integerValue"])
    if "doubleValue" in val_obj:
        return float(val_obj["doubleValue"])
    if "booleanValue" in val_obj:
        return bool(val_obj["booleanValue"])
    if "nullValue" in val_obj:
        return None
    if "timestampValue" in val_obj:
        return val_obj["timestampValue"]
    if "arrayValue" in val_obj:
        vals = val_obj["arrayValue"].get("values", [])
        return [firestore_value_to_python(v) for v in vals]
    if "mapValue" in val_obj:
        fields = val_obj["mapValue"].get("fields", {})
        return {k: firestore_value_to_python(v) for k, v in fields.items()}
    if "referenceValue" in val_obj:
        return val_obj["referenceValue"]
    return val_obj


def dict_to_firestore_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """Converts a Python dictionary to a Firestore fields map."""
    return {k: python_to_firestore_value(v) for k, v in data.items()}


def firestore_doc_to_dict(doc_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Extracts and deserializes a Firestore document object's fields to a Python dictionary."""
    fields = doc_obj.get("fields", {})
    return {k: firestore_value_to_python(v) for k, v in fields.items()}


class FirestoreMCPClient:
    """Synchronous HTTP client for Firestore Remote Model Context Protocol (MCP) Server.

    Executes JSON-RPC 2.0 tool calls (get_document, update_document, list_documents, delete_document)
    over Streamable HTTP against https://firestore.googleapis.com/mcp.
    """

    def __init__(
        self,
        project: Optional[str] = None,
        url: str = DEFAULT_FIRESTORE_MCP_URL,
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
        """Calls a tool on the Firestore Remote MCP Server via JSON-RPC 2.0."""
        from opentelemetry import trace as ot_trace

        headers = get_firestore_auth_headers(credentials=self.credentials)
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }
        tracer = ot_trace.get_tracer("orchestrator.data.firestore_mcp")
        with tracer.start_as_current_span(
            f"firestore.mcp.{tool_name}",
            attributes={
                "db.system": "firestore",
                "mcp.tool": tool_name,
                "mcp.server": "firestore-mcp",
                "net.peer.name": "firestore.googleapis.com",
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

    def get_document(self, collection: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """Fetches a single document by collection and document ID."""
        doc_name = f"projects/{self.project}/databases/(default)/documents/{collection}/{doc_id}"
        result = self._call_tool("get_document", {"name": doc_name}, check_error=False)
        if result.get("isError"):
            content = result.get("content", [])
            err_msg = (
                content[0].get("text", "") if content and isinstance(content, list) and "text" in content[0] else ""
            )
            if "not found" in err_msg.lower():
                return None
            raise RuntimeError(f"MCP tool get_document failed: {err_msg}")

        if "structuredContent" in result and "fields" in result["structuredContent"]:
            return firestore_doc_to_dict(result["structuredContent"])

        content = result.get("content", [])
        if content and isinstance(content, list) and "text" in content[0]:
            try:
                raw = json.loads(content[0]["text"])
                return firestore_doc_to_dict(raw)
            except Exception:
                pass
        return None

    def set_document(self, collection: str, doc_id: str, data: Dict[str, Any]) -> None:
        """Writes or completely overwrites a document by collection and document ID."""
        doc_name = f"projects/{self.project}/databases/(default)/documents/{collection}/{doc_id}"
        doc_payload = {
            "name": doc_name,
            "fields": dict_to_firestore_fields(data),
        }
        self._call_tool("update_document", {"document": doc_payload})

    def update_document(self, collection: str, doc_id: str, updates: Dict[str, Any]) -> None:
        """Applies partial updates to a stored document."""
        existing = self.get_document(collection, doc_id) or {}
        merged = {**existing, **updates}
        self.set_document(collection, doc_id, merged)

    def list_documents(self, collection: str) -> List[Dict[str, Any]]:
        """Lists all documents in a specified top-level collection."""
        parent = f"projects/{self.project}/databases/(default)/documents"
        result = self._call_tool("list_documents", {"parent": parent, "collectionId": collection}, check_error=False)
        if result.get("isError"):
            content = result.get("content", [])
            err_msg = (
                content[0].get("text", "") if content and isinstance(content, list) and "text" in content[0] else ""
            )
            if "not found" in err_msg.lower():
                return []
            raise RuntimeError(f"MCP tool list_documents failed: {err_msg}")

        raw_docs = []
        if "structuredContent" in result and "documents" in result["structuredContent"]:
            raw_docs = result["structuredContent"]["documents"]
        else:
            content = result.get("content", [])
            if content and isinstance(content, list) and "text" in content[0]:
                try:
                    parsed = json.loads(content[0]["text"])
                    raw_docs = parsed.get("documents", [])
                except Exception:
                    pass

        docs: List[Dict[str, Any]] = []
        for doc in raw_docs:
            d = firestore_doc_to_dict(doc)
            if d:
                docs.append(d)
        return docs

    def delete_document(self, collection: str, doc_id: str) -> None:
        """Deletes a document by collection and document ID."""
        doc_name = f"projects/{self.project}/databases/(default)/documents/{collection}/{doc_id}"
        result = self._call_tool("delete_document", {"name": doc_name}, check_error=False)
        if result.get("isError"):
            content = result.get("content", [])
            err_msg = (
                content[0].get("text", "") if content and isinstance(content, list) and "text" in content[0] else ""
            )
            if "not found" in err_msg.lower():
                return
            raise RuntimeError(f"MCP tool delete_document failed: {err_msg}")
