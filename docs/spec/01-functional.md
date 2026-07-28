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
constraints. Ingests current holdings and Chase spending history. Produces
an **Investment Policy Statement (IPS)** — a structured artifact written to
long-term memory — that becomes the reference plan for everything else.
Runs once at onboarding, revisited on drift or major life events.

### Spending Analysis
Analyzes Chase transaction data (BigQuery). Categorizes spend, flags
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
