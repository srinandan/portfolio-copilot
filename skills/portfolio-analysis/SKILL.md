---
name: portfolio-analysis
description: >-
  Measures current holdings against the active Investment Policy
  Statement's target allocation and reports drift. Use when checking
  portfolio health, before considering a rebalance, or when the root
  planner needs current drift to decide whether Action Drafting should
  run.
metadata:
  version: "0.1.0"
  status: draft
manifest:
  id: portfolio-analysis
  summary: >-
    Measures current holdings against the active IPS target allocation and
    reports drift.
  applies_when: >-
    The user asks about portfolio health or drift, or a current drift signal
    is needed before considering a rebalance.
  requires: [active_ips, holdings]
  produces: [drift_report]
  parallelizable: true
---

# portfolio-analysis

## Purpose

Compares current holdings against the active IPS's `target_allocation`
bands and produces a drift report — the signal Action Drafting acts on,
and what a user sees when asking "how's my portfolio doing."

## When this skill runs

- User asks about portfolio health/drift directly
- Root planner invokes it before considering whether to invoke Action
  Drafting (drift is the trigger condition, not a standing schedule — see
  [ADR-0004](../../docs/adr/0004-dynamic-planning-over-fixed-pipeline.md))
- Periodically, if the IPS's `rebalancing_rules.trigger_type` includes
  `calendar` (scheduling mechanism is an orchestrator concern, not
  specified here)

## Inputs

| Field | Source | Required |
|---|---|---|
| [`HoldingsSnapshot`](../../schemas/holdings.schema.json) | Firestore, read-only | Yes |
| Active [`InvestmentPolicyStatement`](../../schemas/ips.schema.json) | Firestore, read-only | Yes — if none exists, see failure mode below |

## Output: Drift Report

Not a persisted contract like the IPS or Holdings — this is a
transient computation, produced and consumed within a single planning
cycle, never written to Firestore on its own. (Contracts in
[`/schemas`](../../schemas) are reserved for persisted, audited
artifacts; this isn't one.)

| Field | Description |
|---|---|
| `asset_class` | One row per IPS `target_allocation` entry |
| `current_percent` | Sum of matching positions' `market_value_usd` ÷ `HoldingsSnapshot.total_value_usd` × 100 |
| `target_percent`, `min_percent`, `max_percent` | From the IPS |
| `in_band` | `true` if `current_percent` is within `[min_percent, max_percent]` |
| `drift_amount_percent` | Distance outside the band; `0` if in band |
| `unclassified_value_usd` | Total value of holdings whose `asset_class` doesn't match any IPS band — reported, not silently dropped from totals |
| `rebalance_recommended` | `true` if any asset class is out of band **and** the IPS's `drift_threshold_percent` is exceeded |

## Failure mode: no active IPS

If no active IPS exists for this user (e.g. before onboarding
completes), this skill declines to run rather than computing drift
against nothing meaningful — surfaces "no investment policy set yet,"
doesn't fabricate a comparison.

## Tools / permissions required

- Managed Agent sandbox: reasons over the orchestrator's pre-computed
  drift report + IPS + holdings context. Formats a `DriftReport` typed
  output with a narrative rationale.
- Orchestrator (outside sandbox): pre-fetches active IPS + holdings from
  Firestore and pre-computes drift via `primitives/portfolio_analysis.py::calculate_drift`
  before invoking the Managed Agent. See [ADR-0016](../../docs/adr/0016-deterministic-primitives-in-orchestrator.md).
- **No** Firestore write access from the Managed Agent. This skill only
  reads and reports; it never drafts or executes anything itself.

## Registry metadata

- Registered as: `projects/{project}/locations/{location}/skills/private-portfolio-analysis`
- Skill revision: 0.1.0 (draft — not yet registered)
- Approval scope: `read:holdings,read:ips`

## Acceptance criteria

1. `current_percent` matches hand-calculated values for a fixed test
   `HoldingsSnapshot` + IPS combination
2. A holding whose `asset_class` matches no IPS band appears in
   `unclassified_value_usd`, and total portfolio value still accounts
   for it — it's never silently excluded
3. `rebalance_recommended` is `true` only when both the out-of-band
   condition and the IPS's `drift_threshold_percent` condition hold —
   tested for boundary cases (exactly at threshold, just under, just over)
4. No active IPS → skill declines to run, doesn't fabricate a report
