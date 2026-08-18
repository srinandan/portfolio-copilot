---
name: research
description: >-
  Gathers external market and news context to inform a potential
  action. Read-only — never has write access to any execution
  capability, and never reads the user's private financial data. Use
  when a proposed or candidate action needs supporting evidence, or the
  user asks about market conditions for a specific holding.
metadata:
  version: "0.1.0"
  status: draft
manifest:
  id: research
  summary: >-
    Gathers external market and news context to inform a candidate action.
    Read-only; never reads the user's private financial data.
  applies_when: >-
    A proposed or candidate action needs supporting evidence, or the user asks
    about market conditions for a specific holding.
  requires: [research_question]
  produces: [research_briefs]
  parallelizable: true
---

# research

## Purpose

Gathers external market/news context — the one skill in this project
with no access to the user's private data at all, by design (see
Isolation, below). Output feeds Action Drafting's `rationale` and
`supporting_research_refs`.

This is the named candidate skill for execution via Managed Agents API,
implemented using ADK's native `ManagedAgent` class (see
[ADR-0009](../../docs/adr/0009-managed-agent-native-class.md), which
refines [ADR-0005](../../docs/adr/0005-managed-agents-hybrid-evaluation.md)
and [ADR-0007](../../docs/adr/0007-skill-content-via-input-not-mounting.md))
— it was chosen specifically *because* it never touches sensitive data,
which is what makes it safe to route through a Pre-GA sandbox in the
first place. The orchestrator constructs a fresh `ManagedAgent` node
each planning cycle, with this file's content resolved from the Agent
Registry as its `description` — not statically configured, and not a
long-lived instance reused across cycles.

## Isolation

This skill has **no** Firestore or BigQuery access. It receives its
research question as a direct input from the orchestrator — it doesn't
look up what to research on its own. This is a deliberate boundary, not
an oversight: it means this skill's tool surface can never grow to leak
private financial data into an external call, regardless of how its
prompt or reasoning evolves.

## When this skill runs

- Root planner invokes it before Action Drafting, when a candidate
  action would benefit from external context (market conditions,
  recent news for a specific ticker)
- User asks a market-conditions question directly

## Inputs

| Field | Source | Required |
|---|---|---|
| `research_question` | Orchestrator — specific tickers or a general market-conditions question, phrased as a direct question, not derived by this skill from user data | Yes |

## Output: Research Brief

Not a persisted contract — transient, like Portfolio Analysis's Drift
Report. Cited by ID from `ProposedAction.supporting_research_refs`
(see [`proposed-action.schema.json`](../../schemas/proposed-action.schema.json)),
so it needs a stable identifier even though the brief itself isn't
stored long-term.

| Field | Description |
|---|---|
| `research_run_id` | Stable ID, referenced by Action Drafting |
| `summary` | Key findings, in the skill's own words |
| `sources` | What was consulted (titles/URLs, not reproduced content) |
| `confidence` | `high` \| `medium` \| `low` |
| `as_of` | Timestamp — market context is time-sensitive |

## Failure mode: no reliable data found

If search/market-data tools don't return anything conclusive, the brief
says so explicitly (`confidence: low`, summary states the gap) rather
than presenting speculation as fact. Action Drafting is expected to
reflect that uncertainty in its own `rationale`, not paper over it.

## Tools / permissions required

- `google_search` (ADK/`ManagedAgent` built-in, server-side) — no custom
  MCP server. `ManagedAgent` doesn't support MCP tools at all; see
  [ADR-0009](../../docs/adr/0009-managed-agent-native-class.md) for why
  this is sufficient for what this skill actually needs, not just a
  limitation worked around.
- **No** Firestore, **no** BigQuery, **no** trade-execution tools of any
  kind. This is the strictest tool surface of any skill in this project.

### Search budget

- **At most 3 `google_search` calls per invocation.** If 3 searches do
  not produce enough evidence, return the brief with `confidence: low`
  and an explicit gap statement in `summary`. Do not keep querying.
- Prefer one broad search followed by at most two follow-ups scoped to
  named tickers, sectors, or dates from the first result. Do not run
  synonym-variant queries of the same question.
- One search per distinct sub-question. If two sub-questions can be
  answered by the same search, run it once.

## Registry metadata

- Registered as: `projects/{project}/locations/{location}/skills/private-research`
- Skill revision: 0.1.0 (draft — not yet registered)
- Approval scope: `read:external_market_data`

## Acceptance criteria

1. This skill's tool surface never includes any internal (Firestore/
   BigQuery) read or write scope — enforced at the tool-list composition
   level, not just documented intent
2. Inconclusive research produces `confidence: low` with an explicit
   gap statement, not a fabricated conclusion
3. Every `ResearchBrief` has a `research_run_id` that Action Drafting
   can cite verbatim in `supporting_research_refs`
4. The `ManagedAgent` node is constructed fresh each planning cycle,
   with `description` resolved from the Agent Registry at that moment —
   not a long-lived instance built once and reused. A revoked skill
   should be absent from the *next* cycle's construction, verified the
   same way as the project's other live-revocation behavior.
