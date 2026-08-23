# Runtime Skills

This directory contains the runtime skills for **Portfolio Copilot**, discovered dynamically at runtime via the Agent Registry.

## Skills Directory

| Skill | Description | Evaluation Suite |
|---|---|---|
| [`goals-onboarding/`](goals-onboarding/) | Conducts user onboarding interview, maps risk tolerance, and synthesizes active IPS and Liabilities snapshots. | [`goals_onboarding.evalset.json`](goals-onboarding/goals_onboarding.evalset.json) |
| [`portfolio-analysis/`](portfolio-analysis/) | Evaluates current portfolio holdings against active IPS target bands and computes drift. | [`portfolio_analysis.evalset.json`](portfolio-analysis/portfolio_analysis.evalset.json) |
| [`action-drafting/`](action-drafting/) | Drafts specific rebalancing orders (`status: drafted`) obeying concentration limits and exclusion rules. | [`action_drafting.evalset.json`](action-drafting/action_drafting.evalset.json) |
| [`spending-analysis/`](spending-analysis/) | Translates spending questions into read-only, user-scoped BigQuery SQL queries and detects anomalies. | [`spending_analysis.evalset.json`](spending-analysis/spending_analysis.evalset.json) |
| [`research/`](research/) | Gathers external market context with strict data isolation via Google Search grounding. | [`research.evalset.json`](research/research.evalset.json) |
| [`reviewer/`](reviewer/) | Independently verifies proposed trades against active IPS, holdings, and concentration limits. | [`reviewer.evalset.json`](reviewer/reviewer.evalset.json) |
| [`equity-research/`](equity-research/) † | Standalone assessment of whether a single equity is attractive on its own merits (DCF, quality ratios, multiples from SEC EDGAR + market quotes). Read-only. | [`equity_research.evalset.json`](equity-research/equity_research.evalset.json) |
| [`suitability/`](suitability/) † | Combines the equity assessment with the user's IPS, holdings, and drift into an advisory buy/add/hold/trim/avoid recommendation. Advisory only. | [`suitability.evalset.json`](suitability/suitability.evalset.json) |

† Advisory equity-research path (see [issue #344](https://github.com/srinandan/portfolio-copilot/issues/344) and [ADR-0027](../docs/adr/0027-equity-research-and-suitability-advisory-analysis.md)). Fully wired: contracts, deterministic primitives (DCF/suitability), manifests, intent/policy routing, planner dispatch (`SKILL_PLANS`, `PIPELINE_SKILL_ORDER`), registration (`register_all_skills.sh`), a synchronous `/api/analysis/equity` endpoint + Portfolio-view card, and ADK evalsets. Live valuations require the skills registered in the Agent Registry (`make register-skills`) and `SEC_EDGAR_USER_AGENT` set (the offline mock fundamentals provider is used otherwise).

## Skill Manifests

Each skill ships a sibling **`manifest.json`** next to its `SKILL.md` — machine-readable
metadata describing the artifacts the skill `requires` / `produces`, whether it is
`parallelizable`, and any structural compliance trigger (`mandatory_if`). This is the
data the planner uses to route by intent and resolve dependencies, per
[ADR-0022](../docs/adr/0022-intent-driven-skill-planning.md). **Structure**
(dependencies) lives here with the skill; **policy** (intent routing) lives with the
planner.

The manifest is kept out of `SKILL.md` on purpose: `SKILL.md` stays clean and
standard-compliant (it carries only the Agent Skills fields), while `manifest.json`
holds the orchestrator-specific routing metadata. The schema, loader, and validation
live in
[`orchestrator/src/orchestrator/skills/manifest.py`](../orchestrator/src/orchestrator/skills/manifest.py);
manifests are graph-validated at orchestrator startup.

```json
{
  "id": "action-drafting",
  "summary": "Drafts a single compliant rebalancing trade from portfolio drift and the active policy.",
  "applies_when": "The user asks to rebalance, trade, buy, sell, or act on portfolio drift.",
  "requires": ["drift_report", "active_ips", "holdings"],
  "optional": ["research_briefs"],
  "produces": ["proposed_action"],
  "parallelizable": false
}
```

## Skill Evaluation with Native ADK

Skills are evaluated using Google's native **Agent Development Kit (ADK)** evaluation framework. Each skill folder contains an `.evalset.json` file defining golden cases, boundary conditions, and guardrail validations adhering to ADK's `EvalSet` schema.

### Running Evaluations

To run an evaluation using the ADK CLI or doc-only evaluation pass:

```bash
# ADK CLI
uv run --project orchestrator adk eval \
  skills/portfolio-analysis \
  skills/portfolio-analysis/portfolio_analysis.evalset.json

# Documentation-Only Agent Pass
PYTHONPATH=. uv run --project orchestrator python -m evals.runner skills/portfolio-analysis
```

For full evaluation architecture and guidelines, see [`docs/evals.md`](../docs/evals.md).
