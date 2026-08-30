# ADR-0033: Safe Parameter Encoding on the BigQuery Remote MCP Path

## Status

**Accepted.** Extends [ADR-0024](0024-bigquery-mcp-orchestrator.md) and [ADR-0029](0029-bigquery-sql-scoping-and-hardening.md).

## Context

ADR-0029 gives Portfolio Copilot's NL-SQL a strong hardening layer in
`orchestrator/data/bigquery.py`: CTE row-scoping to `@user_id`, read-only and
single-statement invariants, `INFORMATION_SCHEMA` blocking, and bound query
parameters. The direct-SDK execution path honours that contract with real
`bigquery.ScalarQueryParameter` bindings.

The **Remote MCP** execution path did not. `BigQueryMCPClient.execute_query`
received the same named `query_parameters` but, because the remote
`execute_sql_readonly` tool accepts only a query string, it resolved them by
**string-interpolating the raw values into the SQL**:

```python
resolved_query = re.sub(rf"@{p_name}\b", f"'{p_val}'", resolved_query)  # unsafe
```

This defeated parameterization on the MCP path: a `STRING` value containing a
single quote broke out of its literal, and the sequential per-parameter
`re.sub` loop could re-scan an already-substituted value (a value containing
`@other` could be reinterpreted as another parameter). The CTE scoping's
tenant-isolation guarantee rests on `@user_id` being an untamperable binding,
so inlining it — and every other string parameter (categories, merchants,
windows) flowing through the shared spending-analysis queries — was a real
injection surface.

## Decision

1. **Encode, never interpolate.** `execute_query` resolves parameters through
   `_resolve_query_parameters`, which renders each value as a safe, type-checked
   BigQuery literal via `_encode_bq_literal`:
   - `STRING` / unknown → single-quoted literal with backslash-escaped escape
     char, quote, and control characters, and embedded NUL dropped.
   - `INT64` / `FLOAT64` / `NUMERIC` → validated numeric (a non-numeric value is
     **rejected**, not pasted in).
   - `BOOL` → `TRUE` / `FALSE`; `None` → `NULL`.
2. **Single-pass substitution.** One `re.sub(r"@(\w+)", repl, query)` pass whose
   replacement output is never re-scanned, so each `@name` is encoded exactly
   once and a value containing an `@token` cannot be reinterpreted. Unknown
   `@tokens` are left intact.

This keeps the existing MCP architecture (the tool still receives a single query
string) while making the MCP path's parameter semantics match the direct-SDK
path's bound parameters end-to-end.

## Consequences

- **Positive:** Closes the injection gap between ADR-0029's guarantees and the
  MCP transport; adversarial `STRING` values (`'`, `;--`, `UNION SELECT`,
  boolean-bypass) can no longer alter query structure, and non-numeric values
  for numeric parameters are rejected fail-closed.
- **Positive:** Fixes a latent double-substitution bug in the previous
  sequential loop.
- **Neutral:** Values are encoded as literals rather than sent as native bound
  parameters, because the remote `execute_sql_readonly` tool takes only a query
  string. If/when the remote tool exposes native parameters, prefer those.
- **Follow-up:** `execute_query` still accepts `maximum_bytes_billed` without
  forwarding it to the remote tool (only the `LIMIT` guardrail from ADR-0029
  bounds MCP-path cost today). Forwarding the byte cap once the remote tool's
  argument name is confirmed is tracked separately.
