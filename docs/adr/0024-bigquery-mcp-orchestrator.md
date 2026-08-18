# ADR-0024: BigQuery Remote MCP Server in Python Agent Orchestrator

## Status
**Accepted.** Extends [ADR-0002](0002-bigquery-plus-firestore-split.md), [ADR-0006](0006-agent-registry-api-alignment.md), [ADR-0008](0008-python-for-orchestrator.md), [ADR-0014](0014-managed-agents-subagent-execution-layer.md), [ADR-0016](0016-deterministic-primitives-in-orchestrator.md), and [ADR-0023](0023-firestore-mcp-orchestrator.md).

## Context
Google Cloud provides an official managed **BigQuery Remote Model Context Protocol (MCP) Server** at `https://bigquery.googleapis.com/mcp` (see [Issue #282](https://github.com/srinandan/portfolio-copilot/issues/282)). The Remote MCP Server exposes standardized LLM tool capabilities (`list_datasets`, `list_tables`, `get_table_schema`, `execute_query`, `explain_query`) over Streamable HTTP / JSON-RPC.

In Portfolio Copilot, banking transaction history and analytics are stored in BigQuery (`portfolio_copilot.checking_transactions`). Data access spans two distinct layers:
1. **Frontend Web Server (`frontend/` & `pkg/bigquery`)**: Written in Go, hosting deterministic REST API endpoints (`/api/spending`) on Cloud Run.
2. **Agent Orchestrator (`orchestrator/`)**: Written in Python, running on Vertex AI Agent Runtime, performing dynamic planning, spending synthesis, and dispatching reasoning tasks.

We evaluate where and how to adopt the BigQuery Remote MCP Server without sacrificing single-roundtrip performance for baseline turn preloading or compile-time type safety in the Go web server.

## Decision

1. **Orchestrator Adopts BigQuery Remote MCP for Dynamic Analytical Queries & Schema Exploration:**
   The Python Agent Orchestrator incorporates the BigQuery Remote MCP Server (`https://bigquery.googleapis.com/mcp`) via ADK's `McpToolset` (`google.adk.tools.mcp_tool.mcp_toolset.McpToolset`). This provides standard tool definitions for dynamic dataset/table discovery, schema inspection, query validation/cost estimation (`explain_query`), and ad-hoc analytical query execution (`execute_query`).

2. **Direct Orchestrator Calling Model (No MCP in Managed Agent Sandbox):**
   The Orchestrator interacts directly with the BigQuery Remote MCP server. The tool is **not** passed into the worker Managed Agent (Antigravity sandbox).
   - **Sandbox Credential Isolation:** Under [ADR-0014](0014-managed-agents-subagent-execution-layer.md) and [ADR-0015](0015-real-user-data-antigravity-sandbox.md), the worker sandbox runs in an isolated environment without production GCP database credentials or query execution tokens.
   - **Deterministic Preloading:** Under [ADR-0016](0016-deterministic-primitives-in-orchestrator.md), mathematical calculations and baseline spending aggregates happen on the orchestrator plane. The worker Managed Agent acts solely as a reasoner over structured `INPUT DATA`.

3. **BigQuery Remote MCP Primary for All Orchestrator Queries with Native SDK Fallback:**
   The Python orchestrator routes spending aggregation queries (`get_spending_snapshot()`, `get_monthly_spending_totals()`, and `get_trailing_income_and_outflow()`) as well as ad-hoc conversational queries (`validate_and_execute_nl_sql()`) through `BigQueryMCPClient.execute_query` (`execute_sql_readonly` tool on `https://bigquery.googleapis.com/mcp`). The native Google Cloud Python SDK (`google-cloud-bigquery`) is retained as an operational fallback for offline/emulator testing and resilience.

4. **Native Go SDK Retained for Web Server & REST Endpoints:**
   The Go web server and shared packages (`pkg/bigquery`) strictly continue using the native Go BigQuery SDK (`cloud.google.com/go/bigquery`). MCP is an LLM reasoning protocol; standard REST handlers require compile-time type safety, static parameterization, and high throughput.

5. **Agent Registry Built-in Service Discovery:**
   Google Cloud first-party MCP servers (including BigQuery) are discoverable via Google Cloud Agent Registry whenever `bigquery.googleapis.com` is enabled in the GCP project. The orchestrator discovers and constructs toolsets via `google.adk.integrations.agent_registry.AgentRegistry.get_mcp_toolset()`.

## Consequences
- Standardizes dynamic dataset exploration, schema queries, and analytical execution on the Model Context Protocol in the agent layer.
- Preserves strict credential isolation for the Managed Agent sandbox.
- Maintains sub-second latency and single-roundtrip efficiency for baseline turn preloading.
- Enforces strict cost guardrails (10MB maximum byte scan limit, user-scoping, and read-only query checks).
- Avoids unnecessary overhead in deterministic Go HTTP services.
