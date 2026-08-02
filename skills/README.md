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
