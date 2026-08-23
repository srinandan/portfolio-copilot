---
name: suitability
description: >-
  Combines a standalone equity assessment with the user's Investment Policy
  Statement, holdings, and allocation drift to produce an advisory buy / add /
  hold / trim / avoid recommendation for a specific stock. Advisory only — it
  never drafts or executes a trade, and is not investment advice.
metadata:
  version: "0.1.0"
  status: draft
---

# suitability

## Purpose

Answers the *personalization* half of "should I buy/sell this stock?": given the
security-only [`EquityAssessment`](../../orchestrator/src/orchestrator/contracts/equity_assessment.py)
from `equity-research`, is this name right **for this user**? It produces an
advisory [`EquityRecommendation`](../../orchestrator/src/orchestrator/contracts/equity_recommendation.py)
— a `buy` / `add` / `hold` / `trim` / `avoid` lean with conviction, transparent
suitability factors, risks, and disclaimers.

**Advisory only.** This skill does not draft a `ProposedAction` and does not
execute anything; the user decides, and any actual order still goes through
`action-drafting → reviewer → the human approval gate`.

## When this skill runs

- After `equity-research`, when the user asked whether a specific ticker is
  worth buying or selling. The planner orders `equity-research → suitability`.

## Deterministic core + advisory narrative

Per the reviewer pattern (ADR-0014), the direction and conviction are decided by
deterministic rules in `primitives/suitability.py`; the LLM layer only explains
them. Decision order (first applicable wins):

1. **Excluded by IPS** → `avoid`
2. **Overvalued** → `trim` if held, else `avoid`
3. **Undervalued + room** (under the concentration limit and the asset-class band
   has room) → `add` if held, else `buy`
4. **Undervalued + no room** (at the concentration limit or the sleeve is full)
   → `hold`
5. **Fairly valued** → `hold`
6. **Unknown** (valuation could not be computed) → `hold`, low conviction

Conviction is capped for `conservative` risk tolerance on a buy/add, and raised
only for `aggressive` tolerance with strong upside into an under-allocated sleeve.

## Inputs

| Field | Source | Required |
|---|---|---|
| `EquityAssessment` | `equity-research` (transient, this cycle) | Yes |
| Active `InvestmentPolicyStatement` | Firestore, read-only (risk tolerance, concentration limit, excluded tickers, target bands) | Yes |
| `HoldingsSnapshot` | Firestore, read-only (current position + weight) | Yes |
| `DriftReport` | `portfolio-analysis` (allocation room), optional | Recommended |
| `UserProfile` | Firestore, read-only (goals/risk notes for narrative), optional | No |

Data access scope: `read:ips`, `read:holdings`.

## Output: EquityRecommendation

Transient (not persisted). Key fields: `direction`, `conviction`, `rationale`,
`valuation_verdict` + `upside_pct` (carried from the assessment), `already_held`,
`current_weight_pct` / `concentration_limit_pct` / `headroom_pct`,
`suitability_factors[]`, `key_risks[]`, and `disclaimers[]` (always present).

## Failure modes

- **No active IPS** → cannot judge suitability; decline rather than assuming a
  policy (consistent with `portfolio-analysis`).
- **`unknown` valuation verdict** → returns `hold` at low conviction and says so;
  it never manufactures a lean from missing data.
