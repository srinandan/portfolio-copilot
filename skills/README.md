# Runtime Skills

This directory contains the runtime skills for **Portfolio Copilot**, discovered dynamically at runtime via the Agent Registry.

## Skills Directory

| Skill | Description | Evaluation Suite |
|---|---|---|
| [`goals-onboarding/`](goals-onboarding/) | Conducts user onboarding interview, maps risk tolerance, and synthesizes active IPS and Liabilities snapshots. | [`EVAL.txtpb`](goals-onboarding/EVAL.txtpb) |
| [`portfolio-analysis/`](portfolio-analysis/) | Evaluates current portfolio holdings against active IPS target bands and computes drift. | [`EVAL.txtpb`](portfolio-analysis/EVAL.txtpb) |
| [`action-drafting/`](action-drafting/) | Drafts specific rebalancing orders (`status: drafted`) obeying concentration limits and exclusion rules. | [`EVAL.txtpb`](action-drafting/EVAL.txtpb) |
| [`spending-analysis/`](spending-analysis/) | Translates spending questions into read-only, user-scoped BigQuery SQL queries and detects anomalies. | [`EVAL.txtpb`](spending-analysis/EVAL.txtpb) |
| [`research/`](research/) | Gathers external market context with strict data isolation via Google Search grounding. | [`EVAL.txtpb`](research/EVAL.txtpb) |

## Skill Evaluation with Evalin

Skills are evaluated using Google's **[evalin](https://g3doc.corp.google.com/learning/gemini/agents/evaluation/evalin/README.md?cl=head)** framework. Each skill folder contains an `EVAL.txtpb` defining golden cases, boundary conditions, and guardrail validations.

### Running Evaluations

To run an evaluation for a specific skill:

```bash
evalin run skills/portfolio-analysis/EVAL.txtpb \
  --with-vs-without-skills \
  --runs=3 \
  --max-parallel=30 \
  --model=flash \
  --judge=flash
```

For full evaluation guidelines, see [`docs/evals.md`](../docs/evals.md).
