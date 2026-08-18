---
name: reviewer
description: >-
  Reviews a drafted ProposedAction against the active Investment Policy
  Statement and rules, producing a ReviewerVerdict with per-rule pass/fail
  results and an overall_pass flag. Runs between Action Drafting and the
  Human-in-the-Loop approval gate.
metadata:
  version: "0.1.0"
  status: draft
---

# reviewer

## Purpose

Validates a drafted `ProposedAction` before it reaches the human. Reads
the active `InvestmentPolicyStatement`, current `HoldingsSnapshot`, and
the `ProposedAction` itself; produces a `ReviewerVerdict` with itemized
`rule_results` and a single `overall_pass` boolean.

Per ADR-0014's defense-in-depth pattern, the LLM's verdict is
**advisory**. The orchestrator re-runs every rule deterministically in
`orchestrator/reviewer/rules.py` and uses **that** verdict for
enforcement. This SKILL.md defines the rules for both — the LLM reasons
over them here, the orchestrator enforces them in code. Any divergence
is audited.

## When this skill runs

- Immediately after Action Drafting produces a `ProposedAction` with
  `status: drafted`
- Before the HITL approval gate (whose gate check reads
  `reviewer_verdict.overall_pass`)
- Before Alpaca execution (which refuses execution when the reviewer
  fails, per ADR-0014)

## Inputs (pre-computed by orchestrator preloader)

| Field | Source | Required |
|---|---|---|
| `proposed_action` | Action Drafting output, drafted this cycle | Yes |
| `active_ips` | Firestore, read-only | Yes |
| `holdings` | Firestore, read-only | Yes |

No BigQuery access. No write access. No external tools.

## Rules to evaluate

For each rule below, produce a `RuleResult` with:
- `rule_id`: exact string as listed
- `description`: short human-readable
- `passed`: true / false
- `detail`: optional explanation, especially when `passed=false`

### `excluded_ticker`
Fails if `proposed_action.ticker` appears in `active_ips.constraints.excluded_tickers`.

### `excluded_sector`
Fails if the sector of `proposed_action.ticker` appears in
`active_ips.constraints.excluded_sectors`. Sector lookup uses the same
static map the orchestrator's `primitives/action_drafting.py::KNOWN_SECTOR_MAP` provides;
if `excluded_sectors` is defined in the IPS and the ticker isn't in the map (sector is `Unknown`),
this rule fails-closed to prevent unverified sector exposure.

### `concentration_limit`
Applies to **buys only**. Fails a buy whose *resulting* position value
(current position + trade value) would exceed
`active_ips.constraints.concentration_limit_percent` of total portfolio
value. A **sell always passes** this rule: a concentration ceiling can
only be breached by adding to a position, and a sell strictly reduces it —
failing a trim because the remaining position is still above the limit
would make an overweight holding (e.g. a broad-market ETF held as the core
sleeve) impossible to unwind. `allocation_band_direction` separately vets
that a sell moves the asset class the right way.

### `allocation_band_direction`
Fails if the trade moves the asset class **away from** the IPS target
band. A sell in an under-allocated asset class fails; a buy in an
over-allocated asset class fails. Uses `primitives/portfolio_analysis.py::calculate_drift`
semantics to determine current-vs-target position of the asset class.

### `ips_version_current`
Fails if `proposed_action.ips_version_referenced` does not match the
currently active IPS version for the user. Guards against a stale IPS
being used to justify a proposal after the user updated their policy.

## Output: `ReviewerVerdict`

```json
{
  "verdict_id": "<uuid>",
  "action_id": "<from proposed_action.action_id>",
  "ips_version_checked_against": {"ips_id": "...", "version": N},
  "rule_results": [
    {"rule_id": "excluded_ticker", "description": "...", "passed": true, "detail": null},
    ...
  ],
  "overall_pass": true|false,
  "requires_human_approval": true|false,
  "reviewer_skill_version": {"skill_name": "private-reviewer", "skill_version": "0.1.0"},
  "reviewed_at": "<ISO-8601 timestamp>"
}
```

**`overall_pass`** is `true` iff every `rule_result.passed` is `true`.

**`requires_human_approval`** — set to `true` when either (a) `overall_pass=false`
(a violation must be surfaced to the human), or (b) the action's
`estimated_value_usd` exceeds `active_ips.approval_required_above_usd`, or
(c) the action's value as a fraction of total portfolio exceeds
`active_ips.approval_required_above_percent`. Per the spec, `requires_human_approval`
can be true even when `overall_pass=true` — high-stakes actions always go to
a human regardless of policy compliance.

## Tools / permissions required

- Managed Agent sandbox: reasons over the orchestrator's pre-computed
  IPS + holdings + ProposedAction context. Produces the typed verdict.
- Orchestrator (outside sandbox): pre-fetches state, invokes the MA,
  re-runs the same rules in deterministic Python code, writes the
  audit entry with both verdicts.
- **No** Firestore, **no** BigQuery, **no** trade-execution tools.
  The reviewer has no way to change state — its output is the verdict.

## Registry metadata

- Registered as: `projects/{project}/locations/{location}/skills/private-reviewer`
- Skill revision: 0.1.0 (draft — not yet registered)
- Approval scope: `read:proposed_action,read:holdings,read:ips`

## Acceptance criteria

1. Every rule produces a `RuleResult` with `passed=true` or `passed=false`
   — no rule is silently skipped; `overall_pass` is the AND of every
   `passed` field.
2. On a happy-path action (no violations), `overall_pass=true`.
3. On any single-rule violation, `overall_pass=false` and the offending
   rule's `passed=false` with a `detail` string.
4. `requires_human_approval` is independently `true` on high-stakes
   actions even when `overall_pass=true`.
5. `ips_version_checked_against` matches the IPS the orchestrator preloaded,
   not a version the LLM invented.
6. The orchestrator's deterministic re-check produces the same
   `rule_results` (for the currently-implemented rule set) — any divergence
   is captured in the audit log's detail field.
