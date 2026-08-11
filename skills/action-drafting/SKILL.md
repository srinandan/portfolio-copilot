---
name: action-drafting
description: >-
  Drafts a specific proposed trade (ticker, side, quantity, order type)
  via Alpaca's paper-trading drafting surface, referencing the active
  Investment Policy Statement. Use only after Portfolio Analysis and
  Research have provided sufficient context — never grants execution
  capability itself.
metadata:
  version: "0.1.0"
  status: draft
---

# action-drafting

## Purpose

Turns a drift signal plus research context into a specific, fully
-specified [`ProposedAction`](../../schemas/proposed-action.schema.json).
This skill's authority ends at `status: "drafted"` — it never executes,
and per [ADR-0005](../../docs/adr/0005-managed-agents-hybrid-evaluation.md)
(resolved), it never will, regardless of how other skills in this
project are implemented.

## When this skill runs

- Portfolio Analysis reports `rebalance_recommended: true` and the root
  planner decides to act on it
- User directly requests a specific trade be evaluated

Action Drafting doesn't invoke itself — the root planner decides to call
it, same as every other skill, per
[ADR-0004](../../docs/adr/0004-dynamic-planning-over-fixed-pipeline.md).

## Inputs

| Field | Source | Required |
|---|---|---|
| Drift Report | Portfolio Analysis (transient, not persisted — see that skill's `SKILL.md`) | Yes |
| Research Brief(s) | Research (transient, not persisted) | Recommended, not strictly required — see failure mode below |
| Active [`InvestmentPolicyStatement`](../../schemas/ips.schema.json) | Firestore, read-only | Yes |
| [`HoldingsSnapshot`](../../schemas/holdings.schema.json) | Firestore, read-only | Yes |
| Current quote | Alpaca, read-only market data endpoint | Yes — for `estimated_price_usd` |

## Drafting logic (deterministic, testable)

Given an over-allocated asset class from the Drift Report:

```
trim_amount_usd = current_asset_class_value_usd
                   - (target_percent / 100 * total_value_usd)
```

Trims back to the IPS's `target_percent`, not merely back inside the
band — bringing a position to just inside `max_percent` would put it at
immediate risk of drifting out again on the next small market move.

**Ticker selection when an asset class has multiple positions:** selects
the single position with the largest market value in that asset class.
Tax-lot optimization, partial-position splitting across multiple
tickers, and gain/loss-aware selection are explicitly out of scope for
this version — a simple, explainable rule beats a sophisticated one that
can't be justified in the `rationale` field a human has to review.

## Pre-check, before drafting (defense in depth)

The Reviewer/Critic is the enforcement backstop, but this skill doesn't
knowingly draft a trade it already knows would fail review:

- Never proposes a ticker in `excluded_tickers` or a sector in
  `excluded_sectors`
- Never proposes a trade that would push the resulting position above
  `concentration_limit_percent`

If the only mathematically-indicated trade would violate either, this
skill declines to draft rather than proposing something it expects the
Reviewer to reject — surfaces the conflict to the user instead (e.g.
"rebalancing would require trimming an excluded ticker — resolve the
exclusion or accept the drift").

## Output

Return **only** the two judgment fields:

- `rationale` — a single paragraph, 2–4 sentences. Cite the drift
  figures from the input's `drift_report` and, if any, the input's
  `research_briefs` by `research_run_id`. If confidence in the research
  is low, say so plainly.
- `supporting_research_refs` — a list of `research_run_id` strings you
  actually cited. Empty list if none apply.

Do NOT restate `ticker`, `side`, `quantity`, `estimated_price_usd`,
`ips_version_referenced`, or any other numeric/identifier field. Those
come from `input.precomputed_trade` and are authoritative. The
orchestrator merges your two fields onto the precomputed trade and
persists the result.

## Failure mode: no research available

If Research was invoked but returned `confidence: low`, this skill still
drafts — the human approval gate exists precisely for judgment calls
under uncertainty — but the low confidence is stated plainly in
`rationale`, not smoothed over. If Research wasn't invoked at all (e.g.
a small, band-boundary rebalance where research adds little), that's a
noted omission in `rationale`, not a silent gap.

## Failure mode: no rebalance warranted

If no asset class is out of band and the user didn't request a specific
trade, this skill drafts nothing. An empty result is a valid, correct
output — never invent a trade to have something to show.

## Tools / permissions required

- Managed Agent sandbox: reasons over the orchestrator's pre-computed
  trade candidate + IPS + holdings + research briefs. Produces a
  `ProposedAction` typed output with `rationale`.
- Orchestrator (outside sandbox):
  - pre-fetches IPS + holdings from Firestore
  - pre-computes the trade math and constraint checks via
    `primitives/action_drafting.py::calculate_draft_action` (excluded
    ticker/sector, concentration limit, IPS-target-band trim math)
  - persists the returned `ProposedAction` to Firestore and emits the
    `ACTION_PROPOSED` audit entry
- Alpaca: **not called at drafting time.** Quote lookups are mocked in
  `primitives/action_drafting.py::get_mock_alpaca_quote`. Only the
  orchestrator's own code calls the real Alpaca endpoint, and only after
  Reviewer pass + human approval (see ADR-0005).
- **No** Alpaca order-placement credential, ever. The Managed Agent
  sandbox holds no broker credentials, per ADR-0005.

## Registry metadata

- Registered as: `projects/{project}/locations/{location}/skills/private-action-drafting`
- Skill revision: 0.1.0 (draft — not yet registered)
- Approval scope: `read:holdings,read:ips,read:market_data_quote`

## Acceptance criteria

1. Trim quantity brings the over-allocated asset class to exactly
   `target_percent`, not merely back inside the band — verified against
   hand-calculated values
2. Never drafts a trade in `excluded_tickers`/`excluded_sectors` — tested
   directly, not only relied on via the Reviewer
3. Never drafts a trade pushing a resulting position over
   `concentration_limit_percent`
4. `ips_version_referenced` always matches the IPS version active at
   drafting time
5. No asset class out of band, no direct user request → zero
   `ProposedAction`s drafted
6. This skill's credential set never includes Alpaca order-placement
   access — enforced at the tool-provisioning level, not just documented
7. Emits an `action_proposed` `AuditLogEntry` on every successful draft
