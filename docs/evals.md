# Skill Evaluations via Native ADK

This document outlines the evaluation framework, schema, and testing workflows for Portfolio Copilot runtime skills using Google's native **Agent Development Kit (ADK)** evaluation framework.

---

## Overview

Runtime skills under `/skills` are dynamically discovered by the root planner via the Agent Registry. To prevent regressions, ensure deterministic compliance with schema invariants, and measure model capabilities, all skills maintain evaluation suites defined in `.evalset.json` files conforming to ADK's `EvalSet` schema.

---

## Evaluation Architecture: Two-Pass Strategy

The ADK evaluation framework supports evaluating the **same converted EvalSet dataset** across two different agent configurations:

```
                      ┌────────────────────────────────────────┐
                      │  Skill EvalSet (*.evalset.json)        │
                      │  - Golden Prompts                      │
                      │  - Invariant Expectations              │
                      │  - Refusal & Boundary Criteria         │
                      └──────────────────┬─────────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
┌─────────────────────────────────┐             ┌─────────────────────────────────┐
│ Pass 1: Documentation-Only Eval │             │ Pass 2: Orchestrator / Live     │
│ (doc_only_agent.py)             │             │ Runtime Skill Eval              │
├─────────────────────────────────┤             ├─────────────────────────────────┤
│ • Stripped LlmAgent             │             │ • Full Orchestrator / Skill     │
│ • Instruction = SKILL.md text   │             │ • Real dynamic planning         │
│ • Tools = [] (Zero tools)       │             │ • Firestore & BigQuery tools    │
│ • Tests: Can an agent with ONLY │             │ • Tests: End-to-end operational │
│   SKILL.md answer correctly?    │             │   behavior & tool interaction   │
└─────────────────────────────────┘             └─────────────────────────────────┘
```

1. **Pass 1: Documentation-Only Eval (`evals/doc_only_agent.py`)**:
   - Builds a minimal `LlmAgent` using the `SKILL.md` file text as its instruction, with **no tools** and no database plumbing.
   - Tests whether `SKILL.md` is self-contained and clear enough for external consumers or registry-discovered agents (e.g. `ManagedAgent`-wrapped Antigravity per [ADR-0009](adr/0009-managed-agent-native-class.md)) to understand rules, thresholds, and guardrails.

2. **Pass 2: Real Orchestrator / Runtime Skill Eval**:
   - Evaluates the deployed orchestrator skill with tool access against the exact same test dataset.
   - Verifies end-to-end execution, database writes, and tool calling.

---

## Skill Evaluation Suites

Each runtime skill folder contains a `.evalset.json` file:

| Skill | EvalSet File | Cases Covered |
|---|---|---|
| [`skills/goals-onboarding/`](../skills/goals-onboarding/) | [`goals_onboarding.evalset.json`](../skills/goals-onboarding/goals_onboarding.evalset.json) | • Initial onboarding & deterministic risk mapping<br>• Conservative drawdown reaction mapping<br>• Life-event IPS versioning & superseding<br>• Refusal of partial persistence on abandoned interviews<br>• Feasibility reality-checks for unrealistic targets |
| [`skills/portfolio-analysis/`](../skills/portfolio-analysis/) | [`portfolio_analysis.evalset.json`](../skills/portfolio-analysis/portfolio_analysis.evalset.json) | • Asset class drift calculation against IPS target bands<br>• Within-band tolerance verification<br>• Unclassified asset reporting without silent omissions<br>• Missing active IPS graceful refusal<br>• Precise boundary evaluation on drift thresholds |
| [`skills/action-drafting/`](../skills/action-drafting/) | [`action_drafting.evalset.json`](../skills/action-drafting/action_drafting.evalset.json) | • Deterministic rebalance trim calculation back to target percent<br>• Excluded ticker and sector constraint enforcement<br>• Single-stock concentration limit guardrails<br>• Strict enforcement of `status: drafted` (no execution authority)<br>• Zero-action output when portfolio is in band<br>• Low-confidence research transparency in rationale |
| [`skills/spending-analysis/`](../skills/spending-analysis/) | [`spending_analysis.evalset.json`](../skills/spending-analysis/spending_analysis.evalset.json) | • Natural-language-to-SQL translation against Chase transactions<br>• Dual-condition anomaly detection (>1.4x avg AND > avg + $100)<br>• Savings rate and emergency cash reserve calculations<br>• Rejection of destructive/write SQL operations<br>• Clarifying question generation for ambiguous queries |
| [`skills/research/`](../skills/research/) | [`research.evalset.json`](../skills/research/research.evalset.json) | • Public market context retrieval via Google Search grounding<br>• Strict isolation (zero private data access)<br>• Transparent reporting of inconclusive data (`confidence: low`)<br>• Rejection of speculative price guarantees |
| [`skills/reviewer/`](../skills/reviewer/) | [`reviewer.evalset.json`](../skills/reviewer/reviewer.evalset.json) | • Enforcement of IPS excluded ticker and sector constraints<br>• Enforcement of concentration limit percent<br>• Verification of target allocation band direction<br>• Active IPS version reference verification |

---

## Running Evaluations

### Running with the ADK CLI

Using the native `adk eval` command:

```bash
uv run --project orchestrator adk eval \
  skills/goals-onboarding \
  skills/goals-onboarding/goals_onboarding.evalset.json
```

### Running the Documentation-Only Evaluation Pass

Use the evaluation runner in `evals/`:

```bash
# Evaluate a single skill
PYTHONPATH=. uv run --project orchestrator python -m evals.runner skills/goals-onboarding

# Evaluate all skills
for dir in skills/*/; do
  PYTHONPATH=. uv run --project orchestrator python -m evals.runner "$dir"
done
```

### CI/CD Evaluation Mode (Judge vs. Heuristic Scoring)

In Continuous Integration (`.github/workflows/skill-evals.yml`), the evaluation suite adapts dynamically to credentials:
- **LLM-Judge Scoring (`--llm-judge`)**: When the `GEMINI_API_KEY` repository secret is present (e.g. on branches within the primary repository), `evals.report --llm-judge` runs model-assisted judging for qualitative evaluation criteria.
- **Heuristic Scoring Only**: When `GEMINI_API_KEY` is absent (e.g. on pull requests from external forks), the CI workflow outputs an explicit warning (`::warning title=LLM Judge Skipped::...`) and gracefully degrades to non-blocking heuristic scoring so PRs can be validated without requiring API secrets.

### Automated Unit Testing

EvalSet schema compliance, JSON validation, and doc-only agent construction are covered by pytest:

```bash
cd orchestrator
PYTHONSAFEPATH=1 uv run pytest tests/test_skill_evalsets.py
```

---

## Guidelines for Adding or Modifying Skills

When creating or modifying a runtime skill in `/skills`:
1. Every new skill **must** include a corresponding `<skill_name>.evalset.json` file in its directory.
2. The eval suite must test golden paths, edge conditions, and failure/refusal modes.
3. Validate that the eval set loads into `google.adk.evaluation.eval_set.EvalSet`.
4. Ensure `SKILL.md` is complete and passes the doc-only agent evaluation.

---

## Live Skill Revocation & Nightly Demos

To ensure runtime governance and skill filtering work end-to-end against live Google Cloud Agent Registry and Vertex AI Sessions services, the repository includes an automated revocation demo (`scripts/demo_live_revocation.py`):
- **Nightly Live Demo**: Configured in `.github/workflows/nightly-demo.yml` (running daily at 05:00 UTC). Runs `scripts/demo_live_revocation.py` against a demo GCP project with `GCP_SA_KEY` and `PROJECT_ID`, verifying two-cycle skill revocation and `SKILL_REVOKED` audit log generation.
- **PR CI Mock Demo**: Configured in `.github/workflows/ci.yml`. Runs `scripts/demo_live_revocation.py --mock-registry` as part of every pull request build without requiring GCP credentials, verifying that the orchestration loop properly filters out revoked skills when excluded from `list_authorized_skills`.

---

## Adversarial Benchmark & Reviewer MA Catch Rate

To benchmark the Reviewer Managed Agent (LLM-alone) catch rate against the deterministic governance gate (`check_all_rules`), run the adversarial benchmark suite:

```bash
# Run adversarial benchmark suite
PYTHONPATH=orchestrator/src uv run --project orchestrator pytest evals/adversarial/test_reviewer_ma_catches.py -v

# Run with live Gemini LLM evaluation (requires GEMINI_API_KEY)
GEMINI_API_KEY=your_key PYTHONPATH=orchestrator/src uv run --project orchestrator pytest evals/adversarial/test_reviewer_ma_catches.py -m live_llm -v
```

This suite measures:
1. `test_deterministic_gate_catches_all`: Asserts that `check_all_rules(review_input)` catches 100% of all canned adversarial violations (concentration, excluded ticker/sector, stale IPS version, allocation band direction) with 0 false positives on valid control cases.
2. `test_reviewer_ma_llm_catch_rate`: Evaluates LLM-alone catch rates across the same adversarial scenarios, generating a summary markdown report table (`reviewer_catch_rate_report.md`) and asserting an LLM catch rate of >= 60% (typically ~70–75% LLM alone vs. 100% with the deterministic gate).
