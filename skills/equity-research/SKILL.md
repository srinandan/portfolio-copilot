---
name: equity-research
description: >-
  Produces a standalone, user-independent assessment of whether a single
  equity is attractive on its own merits — DCF intrinsic value, quality
  ratios, and trading multiples from free public data (SEC EDGAR + market
  quotes). Use when the user asks whether a specific stock is worth buying
  or selling. Read-only; never executes a trade and never gives investment
  advice.
metadata:
  version: "0.1.0"
  status: draft
---

# equity-research

## Purpose

Answers the *security-only* half of "should I buy/sell this stock?" — is the
name attractive **on its own merits**, independent of any user. It produces an
[`EquityAssessment`](../../orchestrator/src/orchestrator/contracts/equity_assessment.py):
a DCF-derived intrinsic value and upside/downside versus the current price,
fundamental quality ratios, the subject's trading multiples, a standalone
valuation verdict (`undervalued` / `fairly_valued` / `overvalued` / `unknown`),
and factual drivers/risks.

Its output feeds the `suitability` skill, which pairs this security-only view
with the user's IPS, holdings, and risk tolerance to produce an advisory
recommendation. This skill has **no** notion of the user.

Methodology adapted from the Apache-2.0 `anthropics/financial-services`
reference skills (`model-builder/dcf-model`, `model-builder/comps-analysis`) —
see the repository `NOTICE`.

## When this skill runs

- The user asks whether a specific ticker is worth buying or selling
  (e.g. "is AAPL a good buy right now?"), or asks to analyze/value a name.
- The root planner selects it before `suitability` when a recommendation is
  requested.

It does not run for imperative trade commands with an explicit quantity
("buy 10 shares of AAPL") — those go to `action-drafting`.

## Deterministic core + advisory narrative

Per the reviewer pattern (ADR-0014), the **numbers of record are deterministic**:
`primitives/equity_research.py` computes the DCF, ratios, and multiples from a
`FundamentalsSnapshot`. The LLM layer only narrates and contextualizes those
numbers — it never invents figures. Any divergence is auditable.

## Inputs

| Field | Source | Required |
|---|---|---|
| `FundamentalsSnapshot` | `executors.EdgarFundamentalsProvider` (SEC EDGAR, primary/free), behind the TTL cache | Yes |
| Latest price | `executors.get_quote` (Alpaca free market data; deterministic mock fallback offline) | Recommended — needed to compute upside and a verdict |
| `ValuationAssumptions` | Defaults in the primitive; overridable (discount rate, terminal growth, projection years) | No |

Data access scope: `read:external_market_data`, `read:fundamentals`. This skill
reads **only public company data** — no Firestore/BigQuery, no user data — so its
tool surface can never leak private financial information (same isolation
rationale as `research`).

## Output: EquityAssessment

Transient (not persisted), like the Drift Report and Research Brief. Key fields:

| Field | Meaning |
|---|---|
| `dcf.intrinsic_value_per_share_usd`, `dcf.upside_pct` | Two-stage DCF value and its gap to the current price |
| `quality` | Net/FCF margin, revenue CAGR, ROE, debt/equity from the latest annual period |
| `multiples` | Subject's P/E, P/FCF, EV/EBIT, market cap |
| `valuation_verdict` | `undervalued` / `fairly_valued` / `overvalued` / `unknown` |
| `confidence` | `high` / `medium` / `low` by data completeness |
| `key_drivers`, `key_risks` | Factual, model-derived points |
| `disclaimers` | Always present — this is not investment advice |

## Failure modes

- **No fundamentals / unknown ticker** → the provider raises; the skill reports
  that it cannot assess the name rather than fabricating figures.
- **Missing FCF or price** → the DCF is skipped and the verdict is `unknown`;
  quality/multiples are still returned where computable. Guessing is never
  substituted for missing data.

## Registry metadata

- Registered as: `projects/{project}/locations/{location}/skills/private-equity-research`
- Skill revision: 0.1.0 (draft — not yet registered)
- Approval scope: `read:external_market_data,read:fundamentals`
