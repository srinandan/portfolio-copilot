# Functional Spec

This document describes what the system does. For how it's built, see
[`02-architecture.md`](02-architecture.md). For why specific decisions were
made, see [`../adr/`](../adr/).

## Core behavior

Given a goal (e.g. "check my portfolio drift" or "should I rebalance"), the
**root planner**:

1. Queries the Agent Registry at runtime for currently-authorized skills
2. Composes a plan dynamically from what it finds — no hardcoded skill
   roster or fixed call sequence
3. Invokes skills as needed to gather information and, if warranted, draft
   a proposed action
4. Decides for itself, based on the action's assessed stakes, whether to
   invoke the Reviewer/Critic and the human-approval gate — these are not
   fixed pipeline stages, they're tools the planner chooses to call
5. Owns final execution of any approved action — this is never delegated

See [ADR-0004](../adr/0004-dynamic-planning-over-fixed-pipeline.md) for why
this is dynamic rather than a fixed pipeline.

## Candidate skills

These are skills the planner *may* discover and compose, not a required
sequence. Each lives in its own directory under [`/skills`](../../skills)
with its own `SKILL.md`.

### Goals & Onboarding
Interviews the user for risk tolerance, goals, time horizon, and
constraints. Ingests current holdings, current liabilities, and checking
spending history. Produces an **Investment Policy Statement (IPS)** — a
structured artifact written to long-term memory — that becomes the
reference plan for everything else, and captures a current
**Liabilities Snapshot** alongside it (debt data self-reported, since
it isn't derivable from checking transactions). Runs during initial onboarding,
revisited on drift, or directly updated via the Profile & Policy hub.

### Profile & Policy Management
Provides a unified settings hub (`/profile`) with 6 dedicated configuration
tabs (Personal & Family, Goals & Timeline, Risk Calibration & Allocation,
Liabilities & Debt, Policy Guardrails, Income & Tax) that captures user demographics
(`UserProfile`), debt obligations (`LiabilitiesSnapshot`), verified tax statements
(`W2Document`), and active portfolio guardrails (`IPS`), with atomic versioning on every update.

### Typed Document Ingestion
Ingests real statement files (`/documents` & `/profile#income`): bank transactions CSVs are
validated and streamed into BigQuery (with deterministic row deduplication),
portfolio holdings, liabilities, and IPS snapshot JSONs are validated against canonical
schemas and stored in Firestore, and IRS Form W-2 tax statements (PDF, PNG, JPEG) are parsed
via Google Cloud Document AI (US W-2 processor) and persisted to Firestore.

### Spending Analysis
Analyzes checking transaction data (BigQuery). Categorizes spend, flags
anomalies, answers trend questions.

### Portfolio Analysis
Measures current holdings against the IPS's target allocation. Reports
drift.

### Research
Gathers external market/news context to inform a potential action.
Read-only — never has write access to any execution capability.

### Action Drafting
Given research and portfolio state, drafts a specific proposed action
(e.g. "sell N shares of X, buy N shares of Y") via the Alpaca paper
trading API's *drafting* surface — no execution capability at this stage.

### Equity Research & Suitability
For a single-name question ("should I buy/sell X?"), two chained skills answer it.
**Equity Research** produces a standalone, user-independent assessment — a
DCF intrinsic value, quality ratios, and trading multiples computed from free
public data (SEC EDGAR fundamentals + market quotes) — and a valuation verdict
(`undervalued`/`fairly_valued`/`overvalued`/`unknown`). **Suitability** then
combines that assessment with the user's IPS (risk tolerance, concentration
limit, exclusions), holdings, and allocation drift into an advisory
`buy`/`add`/`hold`/`trim`/`avoid` recommendation. **Advisory only** — it is
displayed with disclaimers and never drafts or executes a trade; the numbers are
deterministic and the LLM only narrates them. Also exposed synchronously at
`POST /api/analysis/equity` for the Portfolio-view "Research a stock" panel. See
[ADR-0028](../adr/0028-equity-research-and-suitability-advisory-analysis.md).

## Reviewer/Critic

Validates a proposed action against the IPS's policy and risk rules before
it can reach the human. Invoked by the root planner, not a fixed stage.
This is also the layer that must catch the adversarial test scenario (see
[`00-overview.md`](00-overview.md)).

## Human-in-the-loop

- The root planner decides when an action is high-stakes enough to require
  approval — this is a judgment call the planner makes, not a rule applied
  to every action uniformly
- Approval pauses the session (ADK `RequestInput`/resume) and surfaces a
  structured proposal — not prose — for approve / edit / reject
- Only on approval does the root planner execute; it never delegates write
  access to any sub-agent or external harness

## Skills and governance

- Skills follow the Agent Skills open standard (`SKILL.md` +
  YAML frontmatter)
- Skills are sourced from Google Cloud's **Agent Registry**
  (`agentregistry.googleapis.com`) — see
  [ADR-0006](../adr/0006-agent-registry-api-alignment.md) for resource
  naming and the lifecycle-state mechanism this project uses for live
  revocation
- Every action in the audit trail is traceable to: skill name + revision,
  registry entry, and approval scope

## Demo scenarios (acceptance criteria)

1. **Live revocation:** revoke a skill mid-session → next planning cycle
   excludes it, with no error and no session restart
2. **Adversarial test:** inject a poisoned tool result attempting to
   manipulate the agent into an unauthorized action → Reviewer/Critic
   catches it before the human approval gate is ever reached
3. **End-to-end happy path:** goal → dynamic plan → research → proposed
   action → Reviewer pass → human approval → execution → audit log entry
   with full provenance
