---
name: spending-analysis
description: >-
  Synthesizes spending insights, savings rate, and reserve estimates from
  preloaded account transaction facts (e.g. checking_transactions). Use when
  the user asks about spending patterns, budget categories, or when Goals &
  Onboarding needs a savings rate or reserve estimate.
metadata:
  version: "0.2.0"
  status: draft
---

# spending-analysis

## Purpose

Analyzes bank and account transaction data (e.g. `checking_transactions`,
`savings_transactions`): categorizes spend into a fixed taxonomy, flags
anomalies against trailing history, and synthesizes natural language
budgeting insights, savings rate metrics, and reserve months estimates.

Produces typed narrative fields for the orchestrator to merge into the
final SpendingReport.

## When this skill runs

- User asks a direct spending question ("how much did I spend on dining
  last month", "why did X category jump")
- Goals & Onboarding invokes it during interview to estimate savings rate
  and inform the liquidity-needs discussion
- Root planner invokes it ad hoc when a proposed action's rationale would
  benefit from spending context (rare; most paths don't need this)

## Inputs

| Field | Source | Required |
|---|---|---|
| `user_id` | Orchestrator | Yes |
| `query_intent` | Orchestrator — either a specific NL question, or a mode (`categorize`, `anomaly_check`, `savings_rate`) | Yes |
| `preloaded` | Orchestrator — pre-computed BigQuery facts, category totals, savings rate, reserve months, and anomaly checks | Yes |

## Category taxonomy

Transaction category strings from statements are normalized into a fixed internal
taxonomy:

`housing`, `utilities`, `groceries`, `dining`, `transportation`,
`entertainment`, `subscriptions`, `healthcare`, `travel`, `shopping`,
`income`, `transfers`, `fees`, `other`

Unmapped raw categories fall into `other`.

## Deterministic calculations (orchestrator-precomputed)

The orchestrator deterministically computes math and aggregates before
dispatching to the Managed Agent:

1. **Anomaly detection rule:**
   ```
   current_month_spend > (trailing_3_month_average * 1.4)
     AND
   current_month_spend > (trailing_3_month_average + 100)
   ```
2. **Savings rate:**
   `savings_rate = (total_income - total_outflow) / total_income` over trailing 3 months
3. **Reserve months:**
   `reserve_months = HoldingsSnapshot.cash_usd / average_monthly_expenses`

## Output

Return **only** the natural-language synthesis fields:

- `narrative_summary` — 2–5 sentences. Directly answer the user's
  `query_intent` using the preloaded numeric facts. If anomalies were
  flagged by the preloader, name them and give a plausible cause. If
  reserve_months is under 3 or savings_rate is under 0 (spending more
  than earning), call it out. Do not invent numbers; every figure you
  cite must appear in `input.preloaded`. If `input.preloaded` contains
  zero income/outflow and empty categories, state clearly that no transaction
  history is available.
- `anomaly_commentary` — optional list, at most one entry per anomaly
  in `input.preloaded.anomalies`, in the same order. Each string
  replaces the preloader's canned "surged from average" description
  with a more specific explanation (e.g. "one-time medical bill",
  "annual insurance premium"). Leave empty if you have no better
  explanation — the preloader's description is a valid default.

Do NOT restate `total_income_usd`, `total_outflow_usd`, `savings_rate`,
`reserve_months`, `category_breakdown`, or the numeric fields of any
anomaly. Those come from `input.preloaded` and are authoritative. The
orchestrator merges your two fields onto the preloaded facts and
persists the resulting SpendingReport.

## Tools / permissions required

- Managed Agent sandbox: conversational reasoning over preloaded context
- Orchestrator (outside sandbox):
  - BigQuery: read `checking_transactions` / `savings_transactions` (aggregate/`SELECT` only, user-scoped)
  - Firestore: read `holdings` (cash balance only, for reserve estimate)
- **No** direct database execution tools inside the Managed Agent sandbox.

## Registry metadata

- Registered as: `projects/{project}/locations/{location}/skills/private-spending-analysis`
- Skill revision: 0.2.0 (draft — not yet registered)
- Approval scope: `read:spending,read:holdings`
