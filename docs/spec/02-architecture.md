# Architecture

This document describes how the system is built. For what it does, see
[`01-functional.md`](01-functional.md). For the reasoning behind each
decision below, see the linked ADRs.

## Stack summary

| Layer | Choice | ADR |
|---|---|---|
| Agent implementation | Go, ADK 2.0 dynamic workflows | [0001](../adr/0001-go-over-python-for-agents.md) |
| Root orchestration | ADK `DynamicNode` (programmatic control flow, not static graph) | [0004](../adr/0004-dynamic-planning-over-fixed-pipeline.md) |
| Analytical data | BigQuery (Chase transactions) | [0002](../adr/0002-bigquery-plus-firestore-split.md) |
| Transactional data | Firestore (IPS, holdings, liabilities, audit log) | [0002](../adr/0002-bigquery-plus-firestore-split.md) |
| Session state | Vertex AI Sessions | — |
| Long-term memory | Vertex AI Memory Bank | — |
| Deployment / runtime | Vertex AI Agent Engine (Agent Runtime) | — |
| Frontend | TypeScript + Vue.js, Cloud Run | [0003](../adr/0003-standalone-ui-not-agentspace.md) |
| API gateway | Go, Cloud Run | [0003](../adr/0003-standalone-ui-not-agentspace.md) |
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
Root Orchestrator (Go, ADK, Agent Engine)
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
for why.

## Language

Go, for both the orchestrator and the agents themselves. Verified before
committing: ADK 2.0 has full Go/Python parity on the specific capabilities
this project needs — dynamic workflows (both v2.0.0), Memory Bank (Go since
v0.1.0), Agent Engine deployment (Go since v1.2.0), and A2A (exposing +
consuming quickstarts exist for Go). See [ADR-0001](../adr/0001-go-over-python-for-agents.md).

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
