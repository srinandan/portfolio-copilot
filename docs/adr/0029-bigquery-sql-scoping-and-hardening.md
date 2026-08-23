# ADR-0029: CTE-Based Row Scoping and SQL Hardening for BigQuery Natural Language Queries

## Status

**Accepted.** Extends [ADR-0002](0002-bigquery-plus-firestore-split.md), [ADR-0008](0008-python-for-orchestrator.md), [ADR-0016](0016-deterministic-primitives-in-orchestrator.md), [ADR-0024](0024-bigquery-mcp-orchestrator.md), and [ADR-0025](0025-model-armor-floor-settings.md).

## Context

Portfolio Copilot allows conversational and dynamic natural language exploration of banking and spending transaction history stored in BigQuery (`portfolio_copilot.checking_transactions`).

When LLMs or users generate SQL queries dynamically:
1. **Row-Scoping & Tenant Isolation:** In multi-tenant environments, a naive check requiring the literal `@user_id` parameter can be bypassed with boolean injection (e.g. `WHERE user_id = @user_id OR 1=1` or `WHERE 1=1 -- @user_id`).
2. **Metadata & System Catalog Exposure:** Unrestricted queries can join `INFORMATION_SCHEMA` or system metadata views, leaking schema details and dataset topology.
3. **Execution Safety:** Stacked queries (multi-statement injection), write-intent operations (DML/DDL), and unbounded full-table scans pose security and availability risks.

Previously, `pkg/bigquery/bigquery.go` in Go implemented CTE-based query rewriting, but the Python orchestrator's `BigQueryClient.validate_and_execute_nl_sql` only verified substring presence of `@user_id` and basic keywords, leaving an architectural disparity.

## Decision

1. **Mandatory Shadowing CTE for User Row Scoping:**
   All natural language SQL queries in both Python (`orchestrator/data/bigquery.py`) and Go (`pkg/bigquery/bigquery.go`) are automatically rewritten to shadow the targeted transactions table with a Common Table Expression (CTE) scoped strictly to `@user_id`:
   ```sql
   WITH checking_transactions AS (
     SELECT * FROM `project.portfolio_copilot.checking_transactions` WHERE user_id = @user_id
   )
   <clean_user_query>
   ```
   All qualified project/dataset prefixes (e.g. `` `project.dataset.checking_transactions` ``) are stripped prior to wrapping so that all table references in the query resolve unconditionally to the scoped CTE.

2. **Strict Read-Only & Single-Statement Invariants:**
   - Queries must begin with `SELECT` (case-insensitive, after stripping comments).
   - Multi-statement execution is disallowed: any query containing internal semicolons is rejected.
   - Forbidden DDL/DML and execution keywords (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `CREATE`, `ALTER`, `TRUNCATE`, `MERGE`, `EXPORT`, `LOAD`, `CALL`, `EXECUTE`) are blocked across the entire query string.

3. **Metadata & System Catalog Access Blocked:**
   Queries referencing `INFORMATION_SCHEMA` or non-transaction tables are rejected.

4. **Automatic Limit Guardrail & Bounded Cost:**
   - If the query does not contain an explicit `LIMIT \d+` clause, a default `LIMIT 100` is appended.
   - `maximum_bytes_billed` remains enforced at 10 MB per query job across both Remote MCP and direct SDK execution paths.

## Consequences

- **Positive:** Guarantees cryptographic row-level tenant isolation: even if an LLM generates `WHERE 1=1` or malicious filter bypasses, the base dataset exposed to the query contains only the authenticated user's records.
- **Positive:** Unifies query validation semantics and security guarantees across both Go and Python codebases.
- **Positive:** Eliminates SQL injection, stacked statements, DDL/DML mutations, and unauthorized catalog inspection.
- **Neutral:** Natural language queries are restricted to transactions tables; multi-table joins across arbitrary datasets require explicit whitelisted views.
