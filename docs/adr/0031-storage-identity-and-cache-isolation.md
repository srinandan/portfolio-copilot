# ADR-0031: Storage Identity Validation, BOLA Protection, and Session Cache Isolation

## Status

**Accepted.** Extends [ADR-0002](0002-bigquery-plus-firestore-split.md), [ADR-0017](0017-unified-gateway-and-frontend.md), [ADR-0023](0023-firestore-mcp-orchestrator.md), and [ADR-0030](0030-prompt-delimiter-framing-and-isolation.md).

## Context

Portfolio Copilot manages sensitive multi-tenant financial data across Firestore (holdings, liabilities, user profiles, investment policy statements, drift reports, spending reports) and BigQuery analytical tables.

During the runtime security threat model evaluation, three related storage and identity isolation vulnerabilities were identified (Phase 3):
1. **Broken Object-Level Authorization / IDOR (SEC-02):** Unvalidated query parameters or request body identifiers could allow querying or writing documents under arbitrary user identities.
2. **Firestore Path Traversal via User ID (SEC-06):** In both Go and Python clients, document references like `collection("holdings").doc(user_id)` could be manipulated if `user_id` contained forward slashes (e.g. `user_1/subcollection/doc`), navigating into unexpected subcollections.
3. **Cross-Session Global Memory Cache Contamination (SEC-05):** In `orchestrator/src/orchestrator/managed_agents/dispatcher.py`, `_RESEARCH_CACHE` was keyed purely by the research query text without tenant/session namespacing, allowing poisoned research summaries to cross user boundaries.

## Decision

1. **Strict Identifier Validation Format:**
   All user identifiers (`user_id` / `userID`) across both Go (`pkg/store`, `pkg/bigquery`, `frontend/server`) and Python (`orchestrator/data/validation.py`, `orchestrator/data/firestore.py`, `orchestrator/data/bigquery.py`, `orchestrator/server.py`) must conform to the strict identifier regular expression:
   ```
   ^[a-zA-Z0-9_-]{1,64}$
   ```
   - In Go, `ValidateUserID(userID string) error` and `validateUserID(c *gin.Context)` reject non-conforming inputs immediately with HTTP 400 Bad Request or a typed error.
   - In Python, `validate_user_id(user_id: str) -> str` validates inputs at the data client layer and FastAPI Pydantic request models, raising `ValueError` on malformed inputs.

2. **Defense-in-Depth Storage Layer Validation:**
   Both `pkg/store` (Go) and `orchestrator/data/firestore.py` (Python) validate `user_id` before constructing any Firestore collection or document references, ensuring path traversal cannot occur even if an unvalidated call bypasses the HTTP gateway.

3. **Tenant-Namespaced Research Cache:**
   The process-level research cache (`_RESEARCH_CACHE`) in `dispatcher.py` namespaces cache keys by validated `user_id`:
   ```python
   def _research_cache_key(node_input: Any, user_id: Optional[str] = None) -> Optional[str]:
       ...
       uid = user_id or node_input.get("user_id") or "anonymous"
       return f"{uid}:{q.strip().lower()}"
   ```
   This guarantees that research briefs generated for user A are never returned in cache lookups for user B.

4. **Gin Gateway Security Hardening:**
   Adopting Gin web framework security best practices:
   - **Security Headers Middleware:** Sets `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`, `Referrer-Policy: strict-origin-when-cross-origin`, `Content-Security-Policy`, and conditional HSTS `Strict-Transport-Security` over TLS / `X-Forwarded-Proto: https`.
   - **Trusted Proxy Configuration:** Disallows untrusted proxy header spoofing by explicitly configuring `r.SetTrustedProxies(nil)` (or explicit CIDRs via `TRUSTED_PROXIES` environment variable).
   - **Multipart Memory & Body Ceilings:** Sets `r.MaxMultipartMemory = 8 << 20` and applies `MaxBodySizeMiddleware(10 << 20)` on file ingestion routes.

## Consequences

- **Positive:** Closes path traversal vectors in Firestore storage access across Go and Python runtimes.
- **Positive:** Enforces uniform identifier validation at API boundaries, returning structured 400 Bad Request responses for malformed client inputs.
- **Positive:** Completely eliminates cross-session research cache contamination between different users.
- **Positive:** Enforces defense-in-depth HTTP security headers across all API and SPA routes.
- **Positive:** Protects against `X-Forwarded-For` spoofing and memory exhaustion during large file uploads.
- **Neutral:** Rejects user identifiers containing characters outside `[a-zA-Z0-9_-]` or longer than 64 characters.
