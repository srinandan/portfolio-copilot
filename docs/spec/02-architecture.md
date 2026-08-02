# Architecture

This document describes how the system is built. For what it does, see
[`01-functional.md`](01-functional.md). For the reasoning behind each
decision below, see the linked ADRs.

## Stack summary

| Layer | Choice | ADR |
|---|---|---|
| Agent implementation | **Python**, ADK 2.0 dynamic workflows | [0008](../adr/0008-python-for-orchestrator.md) (supersedes [0001](../adr/0001-go-over-python-for-agents.md)) |
| Root orchestration | ADK `DynamicNode` (programmatic control flow, not static graph) | [0004](../adr/0004-dynamic-planning-over-fixed-pipeline.md) |
| Analytical data | BigQuery (Chase transactions) | [0002](../adr/0002-bigquery-plus-firestore-split.md) |
| Transactional data | Firestore (IPS, holdings, liabilities, audit log) — separate Go and Python clients, see [0008](../adr/0008-python-for-orchestrator.md) | [0002](../adr/0002-bigquery-plus-firestore-split.md) |
| Session state | Vertex AI Sessions | — |
| Long-term memory | Vertex AI Memory Bank | — |
| Deployment / runtime | Vertex AI Agent Runtime (Agent Engine) — Python custom-agent contract | [0008](../adr/0008-python-for-orchestrator.md) |
| Deployment identities | Dedicated Cloud Run SAs (`portfolio-copilot-gateway-sa`, `portfolio-copilot-frontend-sa`) + Agent Identity (`orchestrator`) | [0011](../adr/0011-least-privilege-identities.md) |
| Frontend | TypeScript + Vue.js, Cloud Run | [0003](../adr/0003-standalone-ui-not-agentspace.md) |
| API gateway | **Go** (unaffected by the Python pivot — not an agent), Cloud Run | [0003](../adr/0003-standalone-ui-not-agentspace.md), [0008](../adr/0008-python-for-orchestrator.md) |
| Trade execution (paper) | Alpaca API | — |
| Execution layer (evaluating) | Managed Agents API / Antigravity, via Interactions API | [0005](../adr/0005-managed-agents-hybrid-evaluation.md) |

## Data layer

**BigQuery** — Chase transaction data only. Chosen specifically so Spending
Analysis can showcase NL-to-SQL analytics (trend/aggregation questions),
which Firestore's point-read model doesn't support well.

**Firestore** — everything transactional and structural: the IPS document,
portfolio holdings, current liabilities, and the approval/audit log.
Needs millisecond reads, real transactional writes, and row-level
concurrency control — none of which BigQuery is built for.

**Vertex AI Memory Bank** — long-term *soft* memory: preferences, summarized
past interactions, semantic recall (e.g. "rejected trimming AAPL in
March"). Not a substitute for a database — it doesn't hold bulk structured
data.

## Deployment topology

```
Frontend (Vue, Cloud Run)
        │
        ▼
API Gateway (Go, Cloud Run)
  — auth / session token exchange
  — streaming translation
  — fan-out reads (e.g. BigQuery for charts)
  — approval-write path (Firestore audit log + execution trigger)
        │
        ▼
Root Orchestrator (Python, ADK, Agent Runtime)
  — queries Agent Registry at runtime
  — composes plan dynamically (DynamicNode)
  — owns Reviewer/Critic + HITL + final execution
        │
        ▼
Skills (discovered/composed per session)
  — invoked directly (ADK) or via Interactions API (Managed Agents, evaluating)
```

The frontend is a standalone custom UI, not built on Gemini
Enterprise/Agentspace — see [ADR-0003](../adr/0003-standalone-ui-not-agentspace.md)
for why. All Cloud Run services are deployed with `--no-allow-unauthenticated`,
with IAM-authenticated invocation granted from the frontend service account to the gateway
([ADR-0013](../adr/0013-authenticated-cloud-run.md)).

## Deployment identities

Every deployed component operates under a least-privilege, scoped identity (see [ADR-0011](../adr/0011-least-privilege-identities.md) and [ADR-0013](../adr/0013-authenticated-cloud-run.md)):
- **`portfolio-copilot-gateway-sa`** (Cloud Run): Granted `roles/datastore.user` (Firestore audit log + holdings) and `roles/bigquery.dataViewer` (fan-out chart queries). Does not have Secret Manager access.
- **`portfolio-copilot-frontend-sa`** (Cloud Run): Dedicated service account with `roles/run.invoker` on the gateway service (communicates strictly with the Gateway API via authenticated IAM tokens).
- **`orchestrator` Agent Identity** (Agent Runtime): Uses SPIFFE-based per-agent cryptographic identity with `roles/datastore.user`, `roles/bigquery.dataViewer`, and `roles/secretmanager.secretAccessor` (Alpaca API credentials). The Agent Platform Service Agent holds deployment-time secret accessor permissions.


## Language

**Python for the orchestrator and skill logic; Go for the gateway.**
The original choice was Go throughout, verified for capability parity
with Python on ADK 2.0's dynamic workflows, Memory Bank, Agent Engine
deployment, and A2A — all confirmed available in Go. That parity turned
out not to be the deciding factor: Agent Runtime's deployment contract
is documented as Python-only (a class-based contract, not a generic
container interface), which no amount of Go-side feature parity solves.
The gateway isn't an agent and never touches that contract, so it stays
Go. See [ADR-0008](../adr/0008-python-for-orchestrator.md), which
supersedes [ADR-0001](../adr/0001-go-over-python-for-agents.md).

## Lifecycle

Follows the full ADK lifecycle: **define** (agent cards, tool contracts,
approval schema) → **build** → **evaluate** (scenario + adversarial eval
set) → **deploy** (Agent Engine) → **observe** (traces feed the governance
layer).

## Open evaluation: Managed Agents API

Google's Managed Agents API (Pre-GA, Antigravity harness) is being
evaluated as an execution layer for Plan + Research, called from the Go
orchestrator via the Interactions API, using per-interaction tool overrides
to pass a freshly registry-composed MCP tool list on every call. Not yet
committed. See [ADR-0005](../adr/0005-managed-agents-hybrid-evaluation.md)
for the full reasoning, constraints, and the still-open execute-step
question.
