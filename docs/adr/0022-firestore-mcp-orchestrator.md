# ADR-0022: Firestore Remote MCP Server in Python Agent Orchestrator

## Status
**Accepted.** Extends [ADR-0006](0006-agent-registry-api-alignment.md), [ADR-0008](0008-python-for-orchestrator.md), [ADR-0014](0014-managed-agents-subagent-execution-layer.md), and [ADR-0016](0016-deterministic-primitives-in-orchestrator.md).

## Context
Google Cloud provides an official managed **Firestore Remote Model Context Protocol (MCP) Server** at `https://firestore.googleapis.com/mcp` (see [Issue #281](https://github.com/srinandan/portfolio-copilot/issues/281)). The Remote MCP Server exposes standardized LLM tool capabilities for listing collections, querying documents, inspecting schemas, and fetching document records over Streamable HTTP / JSON-RPC.

In Portfolio Copilot, database access exists across two execution environments:
1. **Frontend Web Server (`frontend/` & `pkg/store`)**: Written in Go, hosting deterministic REST API endpoints (`/api/holdings`, `/api/ips`, `/api/spending`, `/api/drift`, `/api/documents`) on Cloud Run.
2. **Agent Orchestrator (`orchestrator/`)**: Written in Python, running on Vertex AI Agent Runtime, executing dynamic planning and dispatching reasoning tasks to a worker Managed Agent.

We evaluate where and how to adopt the Firestore Remote MCP Server without sacrificing compile-time type safety in Go or multi-document ACID transaction guarantees in Python.

## Decision

1. **Orchestrator Adopts Firestore Remote MCP for Agentic Tool Calling:**
   The Python Agent Orchestrator incorporates the Firestore Remote MCP Server (`https://firestore.googleapis.com/mcp`) via ADK's `McpToolset` (`google.adk.tools.mcp_tool.mcp_toolset.McpToolset`). This provides standard tool definitions for dynamic document inspection, schema queries, and profile lookups without hand-rolling bespoke query tools.

2. **Direct Orchestrator Calling Model (No MCP in Managed Agent Sandbox):**
   The Orchestrator interacts directly with the Firestore Remote MCP server. The tool is **not** passed into the worker Managed Agent (Antigravity sandbox).
   - **Sandbox Credential Isolation:** Under [ADR-0014](0014-managed-agents-subagent-execution-layer.md) and [ADR-0015](0015-real-user-data-antigravity-sandbox.md), the Antigravity sandbox runs in an isolated environment without production GCP database credentials or write tokens.
   - **Deterministic Preloading:** Under [ADR-0016](0016-deterministic-primitives-in-orchestrator.md), pure mathematical calculations (`calculate_drift`, `calculate_draft_action`) and state preloading happen strictly on the orchestrator plane. The worker Managed Agent acts solely as a headless reasoner/formatter over structured `INPUT DATA`.

3. **Native Python SDK Retained for ACID Transactions & Audit Invariants:**
   The Python orchestrator retains the native Google Cloud Python SDK (`google-cloud-firestore`) for:
   - **IPS Versioning Invariant:** Multi-document atomic transactions (`@firestore.transactional`) in `_update_ips_transactional()` to atomically supersede version $N$ and create version $N+1$. Remote MCP does not support multi-document transactional locking.
   - **Authoritative Audit Logging:** Fail-closed immutable audit entries (`append_audit_log`) written before returning planner responses.

4. **Native Go SDK Retained for Web Server & REST Endpoints:**
   The Go web server and shared packages (`pkg/store`) strictly continue using the native Go Firestore SDK (`cloud.google.com/go/firestore`). MCP is an LLM reasoning protocol; standard REST handlers require compile-time type safety, JSON schema validation, and high throughput.

5. **Agent Registry Built-in Service Discovery:**
   Google Cloud first-party MCP servers (including Firestore and BigQuery) are built into Google Cloud Agent Registry automatically whenever `firestore.googleapis.com` is enabled in the GCP project. No manual `gcloud agent-registry services create` registration is necessary. The orchestrator can discover and construct toolsets via `google.adk.integrations.agent_registry.AgentRegistry.get_mcp_toolset()`.

## Consequences
- Standardizes dynamic document querying and schema discovery on the Model Context Protocol in the agent layer.
- Preserves strict security isolation for the Managed Agent sandbox.
- Maintains 100% ACID consistency for investment policy statements and fail-closed audit log verifiability.
- Avoids unnecessary overhead in deterministic Go HTTP services.
