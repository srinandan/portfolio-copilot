---
name: spending-analysis
description: >-
  Analyzes Chase transaction data via BigQuery — categorizes spend,
  flags anomalies, answers trend questions via natural-language-to-SQL.
  Use when the user asks about spending patterns, budget categories, or
  wants a trend explained (e.g. "why did dining spend jump in June"), or
  when Goals & Onboarding needs a savings rate or reserve estimate.
metadata:
  version: "0.1.0"
  status: draft
---

# spending-analysis

## Purpose

Analyzes Chase transaction data in BigQuery: categorizes spend into a
fixed taxonomy, flags anomalies against trailing history, and answers
ad hoc trend questions via natural-language-to-SQL — the skill that
showcases the platform's NL-to-SQL capability (see
[ADR-0002](../../docs/adr/0002-bigquery-plus-firestore-split.md) for why
this data lives in BigQuery rather than Firestore).

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
| Chase transactions | BigQuery, read-only | Yes |
| [`HoldingsSnapshot.cash_usd`](../../schemas/holdings.schema.json) | Firestore, read-only | Required only for `savings_rate`/reserve-estimate mode |

## Category taxonomy

Chase's own exported category strings are inconsistent across account
types, so this skill normalizes them into a fixed internal taxonomy
rather than passing them through raw:

`housing`, `utilities`, `groceries`, `dining`, `transportation`,
`entertainment`, `subscriptions`, `healthcare`, `travel`, `shopping`,
`income`, `transfers`, `fees`, `other`

The Chase-category → taxonomy mapping is a maintained lookup table
(implementation detail, not specified turn-by-turn here) — unmapped raw
categories fall into `other` rather than being dropped or erroring.

## Anomaly detection (deterministic, testable)

A category is flagged for a given month if:

```
current_month_spend > (trailing_3_month_average * 1.4)
  AND
current_month_spend > (trailing_3_month_average + 100)
```

Both conditions must hold — the percentage threshold alone would flag
noisy small categories (e.g. a $20 category jumping to $30 is a 50%
increase but not meaningful); the absolute-dollar floor filters that
out.

## Savings rate / reserve estimate

- `savings_rate = (total_income - total_outflow) / total_income` over
  the trailing 3 months
- `reserve_months = HoldingsSnapshot.cash_usd / average_monthly_expenses`
  (average_monthly_expenses = trailing 3-month average outflow)

These feed Goals & Onboarding's `liquidity_needs` discussion — this
skill computes the numbers, Goals & Onboarding decides what to do with
them.

## NL-to-SQL — safety constraints

This is the skill's showcase capability, and also its highest-risk
surface, so the constraints are load-bearing, not optional:

- Generated SQL is **read-only** — `SELECT`/aggregate only. No
  `INSERT`/`UPDATE`/`DELETE`/DDL, ever, regardless of what the natural
  language request implies.
- Every generated query is scoped to the requesting `user_id` — enforced
  at the query-construction layer (a mandatory `WHERE user_id = @user_id`
  parameter), not left to the model to remember to include.
- Query must target only the `chase_transactions` table. No dynamic
  table names from user input.
- A row-count/byte-scan ceiling is enforced (implementation detail: a
  `LIMIT` and a BigQuery maximum-bytes-billed setting) so a malformed or
  adversarial query can't run an expensive full-table scan.

## Failure mode: ambiguous or unanswerable query

If the NL query can't be mapped to a valid, scoped SQL query (ambiguous
category, nonsensical date range), the skill returns a clarifying
question rather than guessing at intent or running a best-effort query
that might silently answer the wrong question.

## Tools / permissions required

- BigQuery: read `chase_transactions` (aggregate/`SELECT` only, user-scoped)
- Firestore: read `holdings` (cash balance only, for reserve estimate)
- **No** write access anywhere. No trade or execution tools.

## Registry metadata

- Registered as: `projects/{project}/locations/{location}/skills/private-spending-analysis`
- Skill revision: 0.1.0 (draft — not yet registered)
- Approval scope: `read:spending,read:holdings`

## Acceptance criteria

1. Every generated SQL query includes the `user_id` scope filter — no
   exceptions, tested against every query mode
2. Anomaly flagging matches the two-condition rule above exactly for a
   range of tested trailing-average/current-month combinations
3. A write-intent NL query ("delete my dining transactions") is refused,
   not translated into an attempted write
4. `savings_rate` and `reserve_months` computations match hand-calculated
   values for a fixed test dataset
5. An unmappable/ambiguous query returns a clarifying question, not a
   best-guess SQL execution
