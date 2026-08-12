# Changelog

All notable changes to Portfolio Copilot are recorded here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this
project intends to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
once tagged. Nothing has been released yet — see the note under `[Unreleased]`.

## [Unreleased]

> This section is a rolling snapshot of everything shipped since project
> inception. When you cut `v0.1.0`, rename this header to
> `## [0.1.0] - YYYY-MM-DD` and start a fresh empty `[Unreleased]` block above.

### Added

**Orchestrator (Python, ADK on Agent Platform Agent Runtime)**
- Registry-driven dynamic planner: at each planning turn, queries the Google
  Cloud Agent Registry for authorized skills and composes a plan from what it
  finds — no hardcoded skill roster (ADR-0004).
- Six runtime skills registered with the Agent Registry:
  `goals-onboarding`, `spending-analysis`, `portfolio-analysis`, `research`,
  `action-drafting`, `reviewer`.
- Managed Agents dispatch: each skill turn is executed by the worker
  Managed Agent with skill-scoped tools and typed output schemas (ADR-0014).
- Deterministic primitives kept in-process (drift, draft-action, spending
  aggregation) — orchestrator pre-computes then hands to the MA (ADR-0016).
- Human-in-the-loop approval gate with approve / edit / reject decisions,
  `MAX_EDIT_ROUNDS` safety cap, and full audit emission on every branch.
- Execution gate placing paper orders against Alpaca with idempotent
  `client_order_id = action_id`; live endpoint never touched.
- Reviewer defense-in-depth: LLM verdict is advisory, orchestrator's
  deterministic re-check is authoritative, and divergence between them is
  captured in the `REVIEW_COMPLETED` audit `detail` field (ADR-0014).
- Live skill revocation detection: planner compares each cycle's authorized
  skills against the previous cycle and emits `SKILL_REVOKED` audit for any
  that disappeared.
- HTTP surface for Agent Runtime custom-container deployment (`/livez`,
  `/readyz`, `POST /v1/invoke`, `POST /v1/resume`, `POST /api/reasoning_engine`,
  `POST /api/stream_reasoning_engine`) built around the same `root_agent`
  workflow that runs in tests.
- OpenTelemetry and Cloud Trace emission on Agent Runtime: injects telemetry environment variables (`GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY`, `OTEL_SEMCONV_STABILITY_OPT_IN`, `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`) and grants `roles/cloudtrace.agent` to Agent Identity (#280).
- Structured onboarding endpoint `POST /v1/onboarding/apply` that persists a
  wizard-collected `GoalsOnboardingResult` directly via
  `write_ips_from_interview_result` — same writer + audit path as the LLM
  interview flow.
- Startup verification of SKILL.md metadata and required secrets, wired into
  the FastAPI `lifespan`.
- Session + Memory Bank via Agent Platform services when `AGENT_ENGINE_ID` is
  set; in-memory fallback for tests.

**Contracts and data**
- Tri-representation contracts (Pydantic + Go structs + JSON Schema) for
  `InvestmentPolicyStatement`, `HoldingsSnapshot`, `LiabilitiesSnapshot`,
  `ProposedAction`, `ReviewerVerdict`, `AuditLogEntry`, `GoalsOnboardingResult`,
  and reports, kept in sync by `scripts/sync-schemas.sh` (CI-checked).
- IPS versioning invariant enforced transactionally on both Python
  (`FirestoreClient.update_ips`) and Go (`store.Client.UpdateIPS`).
- Full governance audit log with 13 event types: `SKILL_INVOKED`,
  `SKILL_INVOCATION_FAILED`, `SKILL_REVOKED`, `IPS_CREATED`, `IPS_SUPERSEDED`,
  `ACTION_PROPOSED`, `REVIEW_COMPLETED`, `APPROVAL_REQUESTED`,
  `APPROVAL_GRANTED`, `APPROVAL_REJECTED`, `ACTION_EXECUTED`, `ACTION_FAILED`,
  `REVIEWER_BYPASSED`. Every entry carries actor identity, skill version,
  registry revision ID, and approval scope.
- BigQuery Chase transactions sandbox: whitelist requires `SELECT` start,
  rejects `MERGE`/`EXPORT`/`LOAD`/`CALL`/`EXECUTE`/multi-statement scripts,
  wraps every query in a CTE that scopes `chase_transactions` to the caller's
  `user_id`, and strips any qualified prefix so the CTE always shadows.
- Streaming progress events (ADR-0018): the planner reports each pipeline
  stage (discovery, per-skill, approval, execution) as advisory
  `{"kind":"progress"}` SSE frames, interleaved with the ADK event stream via a
  context-variable channel (`progress.py`, `server._interleave_progress`), so
  the UI can show live progress during the 2-4 minute analysis. Advisory only —
  never gates execution; the Firestore audit log stays authoritative.

**Frontend (Vue 3 + TypeScript SPA + Go host)**
- Single Cloud Run service serving compiled SPA + `/api/*` in-process
  (ADR-0017) — no cross-service token minting.
- Six-view SPA: Dashboard, Portfolio, Spending, Documents, Security,
  Onboarding.
- 7-step onboarding wizard collecting goals, liabilities, risk calibration,
  target bands, guardrails; submits typed data directly via
  `POST /api/onboarding` (no LLM re-parse of prose).
- Dashboard SSE stream wired to `/api/plan` and `/api/plan/resume`:
  extracts HITL approval requests from the ADK event envelope, renders the
  `<ApprovalCard />`, and drives approve / reject / edit through the
  orchestrator's resume path.
- Live analysis progress stepper (`<AnalysisProgress />`, ADR-0018): routes
  `{"kind":"progress"}` SSE frames into a stage checklist
  (running → done / skipped / failed) with an elapsed timer, then clears and
  replaces it with the final output / approval card when the run completes.
- Empty-state on Dashboard with example prompts before any turn has run.
- Structured logging middleware with GCP-compatible `severity` field and
  `X-Cloud-Trace-Context` propagation.

**Deployment and infrastructure**
- Tag-triggered Cloud Build releases via Developer Connect: pushing a
  `v*` tag builds and deploys orchestrator (Agent Runtime) + frontend
  (Cloud Run) in parallel.
- Per-service Makefiles (`make -C orchestrator deploy`,
  `make -C frontend deploy`) for manual deploys without a tag.
- Setup scripts under `scripts/` for Secret Manager, BigQuery, Firestore,
  Cloud Run, Managed Agent, Agent Runtime, and skill registration; each
  runs standalone and is composed by `setup_all.sh`.
- Least-privilege per-service SAs (frontend, worker, orchestrator agent
  identity) — no default compute SA usage.
- Secret Manager resolution for `ALPACA_API_KEY_ID`, `ALPACA_API_SECRET`,
  and `MANAGED_AGENT_ID` with strict-mode failure at startup in production.

**Testing and CI**
- ~295 Python tests + 66 Vue tests + Go tests across `pkg/{contracts,store,bigquery}`
  and `frontend/server`.
- CI: Python (uv + pytest with coverage + ruff), Go (build + vet + test with
  Firestore emulator + schema-sync check), Frontend (typecheck + build + vitest
  with coverage + Docker build smoke test).
- CodeQL scanning for Go, JavaScript/TypeScript, and Python (currently
  runs without uploading — see Known Limitations below).
- Skill evaluations via ADK evalset with optional Gemini LLM judge.
- Adversarial evals for the reviewer (prompt injection catch-rate benchmark).
- Nightly live-revocation demo workflow.

**Documentation**
- Spec-driven design under `docs/spec/` (overview, functional, architecture,
  contracts).
- 17 ADRs under `docs/adr/` covering key architectural decisions.
- Per-component READMEs (orchestrator, frontend, install, skills).
- `AGENTS.md` for coding-agent contributors, distinguishing runtime skills
  (`/skills`) from engineering-practice skills (`/.agent/skills`).

### Fixed (second-pass review, PR #253)

- `memory_interaction` node no longer writes a hardcoded "user prefers low-risk
  investments" claim into the Memory Bank on every planning turn.
- Frontend HITL approval flow wired end-to-end — approvals now actually
  reach the orchestrator and drive execution rather than mutating client-only
  state.
- Removed REST `/api/proposed_actions/:id/{approve,reject}` endpoints that
  bypassed the HITL gate + audit chain.
- Firestore non-`NotFound` errors return `502 Bad Gateway` instead of demo
  data with `200 OK`.
- BigQuery SQL sandbox switched from a bypassable keyword blocklist
  (missed `MERGE`, `EXPORT DATA`, `EXECUTE IMMEDIATE`, multi-statement
  scripts) to a strict `SELECT`-only whitelist with CTE scoping that
  shadows even fully-qualified table references.
- Orchestrator startup verifications moved from module-import time to
  FastAPI `lifespan` so imports (including test collection) have no side
  effects.
- Reviewer `excluded_sector` rule fails-closed when the IPS defines
  excluded sectors and the ticker's sector cannot be classified.
- `REVIEWER_BYPASSED` audit event emitted whenever
  `PORTFOLIO_COPILOT_ADMIN_BYPASS_REVIEWER=true` skips the reviewer, so
  the escape hatch leaves a ledger trace.
- Onboarding wizard persists collected data directly through the same
  writer the LLM path uses; on failure the UI surfaces the real error
  instead of showing false success.
- Documents view replaced with an honest "coming soon" placeholder (the
  previous version fabricated a `records_parsed: 15` result for any file
  uploaded, with no backend at all).
- Dashboard opens on an empty state with example prompts instead of a
  hardcoded fake AAPL rebalance proposal.
- Frontend `IPSConstraints.account_type` aligned to backend union
  (`'taxable' | 'retirement'`).
- Removed dead `/api/auth-check` (leaked `project_id` metadata) and
  `/api/stream` (5-tick demo) scaffolds and the wildcard CORS middleware
  they lived alongside.
- Removed unused Go Agent Registry client that had drifted to `v1` while
  Python remained on `v1alpha`.
- Frontend `ProposedAction` enum casing normalized to match backend
  serialization; missing status variants (`pending_approval`,
  `reviewed_pass`, `reviewed_fail`) added.

### Deferred to a later release

- **Documents upload**: needs a real POST endpoint, GCS write, parser (CSV
  first, PDF later), and Firestore metadata record.
- **Frontend enum union** still accepts both cases for status/type/side —
  target: normalize on ingest and drop the uppercase variants.
- **Drafting-side sector fail-closed** to mirror the reviewer fix, so
  unclassified-sector tickers never get into the draft in the first place.
- **Structured planner results**: `results.append(...)` still uses an
  f-string with the payload flattened; a structured `{skill, result}` dict
  is cleaner but requires updating ~6 test assertions.
- **Reviewer fallback verdict**: the "IPS/holdings missing" branch of
  `_postprocess_reviewer` currently synthesizes a verdict with empty
  `rule_results`; would be cleaner to raise so `SKILL_INVOCATION_FAILED`
  fires.
- **`secret_loader` test-mode branches**: brittle `Mock`-shape detection
  in production code; targeted cleanup.
- **CodeQL upload**: workflow runs but discards findings
  (`upload: false`); either enable uploads or drop the README badge.

### Known limitations

- Single-user by design (`docs/spec/00-overview.md`) — no multi-tenant
  isolation, no per-user auth boundary beyond Cloud Run IAM.
- Alpaca **paper** trading only; the live endpoint is never wired.
- Reviewer's sector classifier is an 11-ticker hardcoded map; anything
  outside it is classified `Unknown` (reviewer now fails-closed on this
  when the IPS excludes sectors).
- No `CHANGELOG` before this file; earlier history lives in the git log.
- No single source of truth for the project version string yet — a couple
  of `"0.1.0"` literals live in `server.py` and `frontend/package.json`.

---

For pre-release history, see `git log --oneline`.
