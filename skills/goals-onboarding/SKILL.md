---
name: goals-onboarding
description: >-
  Interviews the user for risk tolerance, goals, time horizon, and
  constraints; ingests holdings, liabilities, and Chase spending history;
  produces an Investment Policy Statement (IPS) written to long-term
  memory. Use when onboarding a new user with no active IPS, when the
  user reports a life event affecting their goals, or when Portfolio
  Analysis recommends a drift-triggered policy review.
metadata:
  version: "0.2.0"
  status: draft
---

# goals-onboarding

## Purpose

Interviews the user for risk tolerance, goals, time horizon, and
constraints; ingests current holdings, current liabilities, and Chase
spending history; produces an
[`InvestmentPolicyStatement`](../../schemas/ips.schema.json) — the
reference plan every other skill and the Reviewer/Critic reads against —
and captures a [`LiabilitiesSnapshot`](../../schemas/liabilities.schema.json),
since debt data isn't derivable from Chase transactions alone.

This is the only skill in this project with no path to financial
execution. It reads context and writes policy; it never drafts or
executes a trade. Keep it that way — don't add tool scopes here that
belong to Action Drafting.

## When this skill runs

| Trigger | Meaning | Result |
|---|---|---|
| `initial` | No active IPS exists for this user | Creates version 1 |
| `life_event` | User reports a change (new goal, changed timeline, etc.) mid-conversation | Creates version N+1 |
| `drift_review` | Portfolio Analysis reports drift the current IPS bands don't account for, and recommends revisiting | Creates version N+1, pre-filled with prior answers for the user to confirm or change |

The decision to *invoke* this skill (e.g. noticing a life-event mention)
is the root planner's, not this skill's own — this skill only defines
what it does once invoked, per [ADR-0004](../../docs/adr/0004-dynamic-planning-over-fixed-pipeline.md).

## Inputs

| Field | Source | Required |
|---|---|---|
| `user_id` | Orchestrator | Yes |
| `trigger` | Orchestrator (`initial` \| `life_event` \| `drift_review`) | Yes |
| `existing_ips_ref` | Firestore — active IPS for this user, if any | Required when `trigger != initial` |
| [`HoldingsSnapshot`](../../schemas/holdings.schema.json) | Firestore, read-only | Yes — informs feasibility discussion (e.g. a goal the current portfolio can't plausibly reach) |
| Existing [`LiabilitiesSnapshot`](../../schemas/liabilities.schema.json), if any | Firestore, read-only | Required when `trigger != initial` — presented back to the user to confirm/update rather than re-asked from scratch |
| Chase transaction history | BigQuery, read-only, aggregated | Yes — informs liquidity needs (spending patterns, existing reserve) |
| Interview responses | User, gathered interactively during the skill's own multi-turn conversation | Yes |

The interview itself is multi-turn and not turn-by-turn specified here —
that's an implementation detail. What's specified is the mapping from
interview content to IPS fields, below.

## Interview → IPS field mapping

**Goals.** Free-form goal name, target amount, target date — one or more.
Each becomes a `goals[]` entry. Reality-check against current holdings +
savings rate (derived from Chase data); if a goal's target is
implausible given the timeline, flag it to the user during the interview
— don't silently accept or silently block.

**Liabilities.** Asked directly, one entry per debt: type (credit card,
mortgage, auto loan, student loan, HELOC, other), balance, interest
rate, minimum payment. If an existing `LiabilitiesSnapshot` was passed in
(revision triggers), present it back for the user to confirm or update
rather than re-asking from scratch. Written as a
[`LiabilitiesSnapshot`](../../schemas/liabilities.schema.json) —
separately from the IPS, since it's current-state data that changes on
its own schedule (a credit card balance moves monthly; policy doesn't).

*Not yet in scope:* this data isn't automatically factored into the
`risk_tolerance` mapping below. High-interest debt arguably should
temper an otherwise-aggressive allocation (risk *capacity* vs. risk
*tolerance*) — the field exists so a future Reviewer rule or an explicit
prompt to the user ("you're carrying 22% APR debt — still want an
aggressive allocation?") can use it. Wiring that logic in is a
deliberate next decision, not an oversight to silently paper over here.

**Risk tolerance.** Not asked directly ("are you conservative or
aggressive?") — derived deterministically from two questions, so the
mapping is testable rather than a judgment call buried in a prompt:

1. Time horizon in years (for the primary goal)
2. Reaction to a hypothetical 20% portfolio drawdown: `sell` / `hold` /
   `buy_more`

| time_horizon_years | drawdown_reaction | → risk_tolerance |
|---|---|---|
| ≥ 15 | `hold` or `buy_more` | `aggressive` |
| ≥ 7 | `hold` or `buy_more` | `moderate` |
| any | `sell` | `conservative` |
| < 7 | `hold` or `buy_more` | `moderate` |

**Time horizon.** Directly from the primary goal's target date.

**Liquidity needs.** `reserve_months` asked directly; `known_upcoming_expenses_usd`
summed from user-reported near-term expenses.

**Target allocation.** Propose default bands per risk tier (below) as a
starting point; user can override any band before confirming. Never
finalize without an explicit confirmation step — this is the one place
in the skill where the interactive interview itself functions as the
approval gate, since there's no separate Reviewer/HITL step for policy
changes (only for trades).

| risk_tolerance | Default target (min–max band) |
|---|---|
| `conservative` | equity 30% (20–40), bonds 60% (50–70), cash 10% (5–15) |
| `moderate` | equity 60% (50–70), bonds 30% (20–40), cash 10% (5–15) |
| `aggressive` | equity 85% (75–95), bonds 10% (0–20), cash 5% (0–10) |

**Constraints.** `excluded_tickers`/`excluded_sectors` asked directly
(optional, default empty). `concentration_limit_percent` defaults to 15,
user-overridable. `account_type` and `tax_loss_harvesting_enabled` asked
directly.

**Approval thresholds.** `approval_required_above_usd` and
`approval_required_above_percent` — asked directly, with a suggested
default (e.g. $1,000 or 5% of portfolio, whichever is lower) the user can
adjust.

## Output

Produces a typed [`GoalsOnboardingResult`](../../schemas/ips.schema.json)
carrying the synthesized interview responses. The trusted orchestrator
validates this structured output and executes the corresponding Firestore
writes:

1. One [`InvestmentPolicyStatement`](../../schemas/ips.schema.json) instance,
   written to Firestore, **plus**
2. One [`LiabilitiesSnapshot`](../../schemas/liabilities.schema.json), written
   or overwritten in Firestore (current-state, not versioned — unlike the
   IPS below, there's no history to preserve here, the latest snapshot
   simply replaces the prior one).

**Versioning invariant (IPS only):** exactly one document with
`status: "active"` per `ips_id` at any time.

- `trigger: initial` → write version 1, `status: "active"`.
- `trigger: life_event` or `drift_review` → write version N+1 with
  `status: "active"`, **and** update the previous active version's
  document: `status → "superseded"`, `superseded_by → "{ips_id}:v{N+1}"`.
  These two writes happen together — never leave two active versions, or
  zero.

A summarized version (risk tolerance, goals, key constraints — not the
full document) is also pushed by the orchestrator to Agent Platform Memory Bank
for semantic recall in future sessions.

## Failure mode: incomplete interview

If the user abandons the interview before all required IPS fields are
answered, the Managed Agent does not emit a complete result and **no
documents are written** — neither the IPS nor the `LiabilitiesSnapshot`.
Partial state is never persisted: a half-complete IPS would fail schema
validation, and a document that doesn't validate should never exist in
Firestore. Resume from where the user left off on the next invocation rather
than starting over, if practical.

## Tools / permissions required

- Managed Agent sandbox: conversational interaction with the user (`RequestInput`)
- Orchestrator (outside sandbox):
  - Firestore: read `holdings`, read `liabilities`, read/write `ips`, write `liabilities`, write `audit_log`
  - BigQuery: read `chase_transactions` (aggregate queries only)
  - Agent Platform Memory Bank: write (summarized preferences)
- **No** trade-execution tools, no Alpaca access, no write access inside the sandbox.

## Registry metadata

- Registered as: `projects/{project}/locations/{location}/skills/private-goals-onboarding`
  (self-registered skills are namespaced under the `private-` publisher
  prefix — see [ADR-0006](../../docs/adr/0006-agent-registry-api-alignment.md))
- Skill revision: 0.2.0 (draft — not yet registered)
- Approval scope: `read:holdings,read:liabilities,read:spending,read:ips`

## Acceptance criteria

1. `trigger: initial`, no existing IPS → produces exactly one IPS
   document, version 1, `status: active`, valid against `ips.schema.json`,
   plus one `LiabilitiesSnapshot` valid against `liabilities.schema.json`
2. `trigger: life_event` or `drift_review` with an existing active IPS →
   produces version N+1 `active`; previous version flips to `superseded`
   with `superseded_by` set; exactly one active version exists afterward;
   `LiabilitiesSnapshot` is overwritten, not versioned
3. Interview abandoned mid-way → zero documents written (neither IPS nor
   `LiabilitiesSnapshot`)
4. `risk_tolerance` is set via the mapping table above for every tested
   `(time_horizon_years, drawdown_reaction)` combination — not free-form
5. Default `target_allocation` bands match the risk-tier table and are
   overridable before the write occurs
6. On a revision trigger, an existing `LiabilitiesSnapshot` is presented
   back to the user rather than re-collected from scratch
7. Emits `AuditLogEntry` records: `skill_invoked` at start, `ips_created`
   (initial) or `ips_superseded` (revision) on write — see
   [`audit-log-entry.schema.json`](../../schemas/audit-log-entry.schema.json)

## Non-goals

The risk-tolerance mapping above is a simplified deterministic heuristic
for demo purposes — it is not a licensed suitability assessment and
shouldn't be presented as one. See project-level non-goals in
[`00-overview.md`](../../docs/spec/00-overview.md).
