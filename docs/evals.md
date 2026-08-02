# Skill Evaluations

This document outlines the evaluation framework and testing workflows for Portfolio Copilot runtime skills using Google's **[evalin](https://g3doc.corp.google.com/learning/gemini/agents/evaluation/evalin/README.md?cl=head)** infrastructure.

---

## Overview

Runtime skills under `/skills` are dynamically discovered by the root planner via the Agent Registry. To prevent regressions, ensure deterministic compliance with schema invariants, and measure model capabilities, all skills maintain evaluation suites defined in `EVAL.txtpb` files.

---

## Evaluation Framework: Evalin

[Evalin](https://g3doc.corp.google.com/learning/gemini/agents/evaluation/evalin/README.md?cl=head) is the standardized evaluation harness for Gemini/Jetski agent skills.

### Key Capabilities

- **Skill Uplift Measurement (`--with-vs-without-skills`)**: Evaluates agent performance both with and without the skill enabled to quantify performance delta and verify that the skill adds demonstrable value.
- **LLM-as-a-Judge Evaluation**: Uses Gemini Flash to grade trajectory outputs, semantic compliance, and adherence to safety constraints.
- **Multi-Run Consistency**: Executes multiple trials per test case (`--runs=3`) to ensure statistical reliability across stochastic completions.
- **Trajectory & Error Reporting**: Generates shareable evaluation reports (`EVALIN_REPORT`) and trajectory visualizer links.

---

## Skill Evaluation Suites

Each runtime skill contains an `EVAL.txtpb` test suite covering:
1. **Golden Path Scenarios**: Standard expected user interactions with explicit ground-truth expectations.
2. **Boundary & Threshold Conditions**: Edge cases around mathematical boundaries (e.g. drift threshold borders, concentration ceilings).
3. **Guardrails & Safety Invariants**: Enforcement of read-only constraints, exclusion lists, refusal on missing prerequisites, and human-in-the-loop approval gates.

### Summary of Test Suites

| Skill | Test Cases Covered |
|---|---|
| [`skills/goals-onboarding/EVAL.txtpb`](../skills/goals-onboarding/EVAL.txtpb) | - Initial onboarding & deterministic risk mapping<br>- Conservative drawdown reaction mapping<br>- Life-event IPS versioning & superseding<br>- Refusal of partial persistence on abandoned interviews<br>- Feasibility reality-checks for unrealistic targets |
| [`skills/portfolio-analysis/EVAL.txtpb`](../skills/portfolio-analysis/EVAL.txtpb) | - Asset class drift calculation against IPS target bands<br>- Within-band tolerance verification<br>- Unclassified asset reporting without silent omissions<br>- Missing active IPS graceful refusal<br>- Precise boundary evaluation on drift thresholds |
| [`skills/action-drafting/EVAL.txtpb`](../skills/action-drafting/EVAL.txtpb) | - Deterministic rebalance trim calculation back to target percent<br>- Excluded ticker and sector constraint enforcement<br>- Single-stock concentration limit guardrails<br>- Strict enforcement of `status: drafted` (no execution authority)<br>- Zero-action output when portfolio is in band<br>- Low-confidence research transparency in rationale |
| [`skills/spending-analysis/EVAL.txtpb`](../skills/spending-analysis/EVAL.txtpb) | - Natural-language-to-SQL translation against Chase transactions<br>- Dual-condition anomaly detection (>1.4x avg AND > avg + $100)<br>- Savings rate and emergency cash reserve calculations<br>- Rejection of destructive/write SQL operations<br>- Clarifying question generation for ambiguous queries |
| [`skills/research/EVAL.txtpb`](../skills/research/EVAL.txtpb) | - Public market context retrieval via Google Search grounding<br>- Strict isolation (zero private data access)<br>- Transparent reporting of inconclusive data (`confidence: low`)<br>- Rejection of speculative price guarantees |

---

## Running Evaluations

### Local & Presubmit Execution

Run `evalin` against a specific skill suite:

```bash
evalin run skills/portfolio-analysis/EVAL.txtpb \
  --with-vs-without-skills \
  --runs=3 \
  --max-parallel=30 \
  --model=flash \
  --judge=flash
```

To run across all skills:

```bash
for skill in skills/*/EVAL.txtpb; do
  echo "Evaluating $skill..."
  evalin run "$skill" --with-vs-without-skills --runs=3 --model=flash --judge=flash
done
```

---

## Guidelines for Adding or Modifying Skills

When creating or modifying a skill in `/skills`:
1. Every new skill **must** include a corresponding `EVAL.txtpb` file in its directory.
2. The eval suite must test golden paths, edge conditions, and failure/refusal modes.
3. Include the generated `EVALIN_REPORT` URL in pull request descriptions and code reviews.
