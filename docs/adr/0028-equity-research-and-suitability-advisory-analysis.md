# ADR-0028: Advisory Equity Research & Suitability (Single-Name Buy/Sell Analysis)

## Status

Accepted

## Context

Portfolio Copilot's trade reasoning was entirely **IPS/allocation-driven**: `portfolio-analysis` measures drift against the active Investment Policy Statement, and `action-drafting` sizes a **sell** to trim an over-allocated asset class back to target. There was no notion of whether a *specific security* was attractive on its own merits — no valuation, no fundamentals, no earnings/quality signal.

Concretely, a prompt like *"should I buy more AAPL now?"* was classified as a trade intent (the keyword `buy`) and routed to `action-drafting`, whose deterministic logic only trims over-allocations. The only external connector was Alpaca, and even its quote was mocked; there was no fundamentals data source anywhere.

We want to answer *"is this a good buy/sell for me?"* — a standalone view of the security **plus** a fit-to-user judgment — while preserving the project's human-in-the-loop, never-auto-execute, not-financial-advice posture.

## Decision

### 1. Two chained skills: `equity-research` → `suitability`

- **`equity-research`** produces a *user-independent* `EquityAssessment`: a two-stage DCF (explicit free-cash-flow projection discounted at a WACC proxy plus a Gordon-growth terminal value, less net debt, per diluted share), fundamental quality ratios, trading multiples, and a `valuation_verdict` (`undervalued` / `fairly_valued` / `overvalued` / `unknown`). It has **no access to user data** — the same isolation rationale as `research`.
- **`suitability`** combines that assessment with the user's IPS (risk tolerance, single-position concentration limit, excluded tickers, target bands), current holdings, and allocation drift to produce an advisory `EquityRecommendation` (`buy` / `add` / `hold` / `trim` / `avoid`) with conviction, transparent suitability factors, risks, and disclaimers.

Separating the standalone assessment from personalization keeps the valuation reusable and independently testable, and mirrors the existing `portfolio-analysis → action-drafting` split.

### 2. Deterministic core + advisory LLM (mirrors ADR-0014)

Per the reviewer's defense-in-depth pattern, the **numbers of record are deterministic**: `primitives/equity_research.py` and `primitives/suitability.py` compute the DCF, ratios, direction, and conviction. The worker Managed Agent (LLM) only narrates them; it never invents figures. Every missing input is guarded and yields `unknown` rather than a fabricated value.

### 3. Free data, pluggable provider, offline mock

- **SEC EDGAR** (`data.sec.gov`) is the primary, uncapped, free source of as-reported XBRL financials — the inputs to DCF and comps. It requires a descriptive `SEC_EDGAR_USER_AGENT`.
- **Alpaca** (already used for paper execution) supplies free market quotes.
- Fundamentals sit behind a `FundamentalsProvider` interface with a TTL cache; a free fundamentals API (e.g. Finnhub) for extras can be added without touching consumers. A `MockFundamentalsProvider` (à la `MockW2Parser`) keeps the whole path runnable offline and deterministic in CI.

### 4. Advisory only

Neither skill drafts a `ProposedAction` or executes anything. The recommendation is displayed with mandatory not-investment-advice disclaimers; the user decides, and any actual order still flows through `action-drafting → reviewer → the human approval gate`.

### 5. Intent routing (disambiguate advice vs. trade command)

A new, high-precision `requested_equity_analysis` intent signal recognizes single-name advice ("should I buy AAPL?", "is TSLA worth buying?", "AAPL valuation") and is kept distinct from portfolio-level rebalancing ("trim my tech exposure") and imperative trade commands ("buy 10 shares"). A policy `equity-analysis-include` rule pulls in `equity-research → suitability`; the manifest `requires`/`produces` graph orders them (`suitability` consumes the `equity_assessment` that `equity-research` produces).

### 6. Synchronous deterministic API + UI

Because the recommendation core needs no LLM, the UI path is a **synchronous** endpoint — `POST /v1/analysis/equity` — that runs the two preloaders directly and returns `{ticker, assessment, recommendation}`, bypassing the streaming planner (mirroring the `/v1/onboarding/apply` precedent). The Go server proxies it at `/api/analysis/equity`, and the Vue Portfolio view renders an advisory `EquityRecommendationCard`.

### 7. Attribution

The valuation/comps/quality methodology is adapted from the Apache-2.0 `anthropics/financial-services` reference skills (`model-builder`, `earnings-reviewer`, `market-researcher`); no source files were copied verbatim. See the repository `NOTICE`.

## Consequences

- **Positive:** Answers "should I buy/sell X?" with a real, transparent, deterministic valuation and a suitability-aware advisory lean — a capability the IPS-only planner lacked.
- **Positive:** Zero incremental cost (SEC EDGAR + Alpaca free tiers); fully offline-testable via the mock provider.
- **Positive:** Preserves the never-auto-execute, not-advice posture; the advisory output is decision support, not a directive.
- **Neutral:** The advisory path is recall-biased — an equity-advice prompt also keeps the trade path, which self-skips without a quantity.
- **Neutral:** Live valuations require the two skills registered in the Agent Registry (`make register-skills`) and `SEC_EDGAR_USER_AGENT` set; otherwise the deterministic mock provider is used. The synchronous endpoint requires `ORCHESTRATOR_URL` (direct mode), like onboarding-apply.
- **Negative / limits:** Free fundamentals-API tiers are personal/non-commercial; a commercial deployment would need a paid tier. The DCF is assumption-sensitive by nature, and forward estimates are model-derived (EDGAR is historical filings only).

## Alternatives considered

- **Deploy the FSI plugins via the Anthropic Managed Agents API** — rejected; the project does not use that API and adding an external runtime was unnecessary. Adapting the methodology into the existing skill + `primitives/` pattern is simpler and free.
- **A paid fundamentals API (FMP, etc.)** — rejected for v1 on the zero-cost constraint; SEC EDGAR plus a free tier suffices, and the provider is pluggable to a paid tier later.
- **One combined `equity-analysis` skill** — rejected; separating standalone valuation from personalization keeps the valuation reusable and testable and matches the Portfolio-Analysis → Action-Drafting split.
- **Reimplementing the DCF in the Go backend** — rejected; it would duplicate the Python primitives. The synchronous orchestrator endpoint reuses the exact deterministic core.
