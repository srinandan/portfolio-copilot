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

## Skill Manifests

Each skill's `SKILL.md` front-matter carries a `manifest:` block — machine-readable
metadata describing the artifacts the skill `requires` / `produces`, whether it is
`parallelizable`, and any structural compliance trigger (`mandatory_if`). This is the
data the planner uses to route by intent and resolve dependencies, per
[ADR-0022](../docs/adr/0022-intent-driven-skill-planning.md). **Structure**
(dependencies) lives here with the skill; **policy** (intent routing) lives with the
planner. The schema, loader, and validation live in
[`orchestrator/src/orchestrator/skills/manifest.py`](../orchestrator/src/orchestrator/skills/manifest.py);
manifests are graph-validated at orchestrator startup.

```yaml
manifest:
  id: action-drafting
  summary: >-
    Drafts a single compliant rebalancing trade from portfolio drift and the active policy.
  applies_when: >-
    The user asks to rebalance, trade, buy, sell, or act on portfolio drift.
  requires: [drift_report, active_ips, holdings]
  optional: [research_briefs]
  produces: [proposed_action]
  parallelizable: false
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
