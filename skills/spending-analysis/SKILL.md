---
name: spending-analysis
description: >-
  Analyzes Chase transaction data via BigQuery — categorizes spend,
  flags anomalies, answers trend questions via natural-language-to-SQL.
  Use when the user asks about spending patterns, budget categories, or
  wants a trend explained (e.g. "why did dining spend jump in June"), or
  when Goals & Onboarding needs a savings rate or reserve estimate.
metadata:
  version: "0.2.0"
  status: draft
---

# spending-analysis

## Purpose

Analyzes Chase transaction data: categorizes spend into a fixed taxonomy,
flags anomalies against trailing history, and synthesizes natural language
budgeting insights, savings rate metrics, and reserve months estimates.

Produces a typed [`SpendingReport`](../../schemas/spending-report.schema.json)
for the orchestrator and downstream skills.

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

Chase's own exported category strings are normalized into a fixed internal
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

Produces a typed [`SpendingReport`](../../schemas/spending-report.schema.json)
containing:
- `user_id`: string
- `total_income_usd`: float
- `total_outflow_usd`: float
- `savings_rate`: float
- `reserve_months`: float
- `category_breakdown`: list of CategorySpending
- `anomalies`: list of SpendingAnomaly
- `narrative_summary`: natural language synthesis and recommendations

## Tools / permissions required

- Managed Agent sandbox: conversational reasoning over preloaded context
- Orchestrator (outside sandbox):
  - BigQuery: read `chase_transactions` (aggregate/`SELECT` only, user-scoped)
  - Firestore: read `holdings` (cash balance only, for reserve estimate)
- **No** direct database execution tools inside the Managed Agent sandbox.

## Registry metadata

- Registered as: `projects/{project}/locations/{location}/skills/private-spending-analysis`
- Skill revision: 0.2.0 (draft — not yet registered)
- Approval scope: `read:spending,read:holdings`
