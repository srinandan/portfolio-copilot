# Portfolio Copilot

[![CI](https://github.com/srinandan/portfolio-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/srinandan/portfolio-copilot/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/srinandan/portfolio-copilot)](./LICENSE)
[![Go Version](https://img.shields.io/github/go-mod/go-version/srinandan/portfolio-copilot?filename=go.mod)](./go.mod)
[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](./orchestrator/pyproject.toml)
[![Node Version](https://img.shields.io/badge/node-20+-green.svg)](./frontend/package.json)
[![CodeQL](https://github.com/srinandan/portfolio-copilot/actions/workflows/codeql.yml/badge.svg)](https://github.com/srinandan/portfolio-copilot/actions/workflows/codeql.yml)

Portfolio Copilot is an experimental personal finance assistant built on Google Cloud's Gemini Enterprise Agent Platform. It uses dynamic runtime planning rather than static execution graphs: given a user objective, the root agent discovers currently available capabilities, drafts an execution plan, evaluates policy constraints, and requires explicit human approval before executing any trade actions.

> **Disclaimer:** This repository is an educational demo and reference implementation. It does not provide financial advice, and all trade execution is wired strictly to Alpaca's paper trading sandbox.

---

## Key Capabilities

- **Dynamic Runtime Planning:** Rather than relying on hardcoded workflows, the planner discovers registered skills at runtime and composes execution plans dynamically.
- **Hot-Pluggable Capabilities:** Skills can be enabled or revoked mid-session; the planner recalculates its task graph on the subsequent step without restarting.
- **Human-in-the-Loop Trade Gate:** Proposed actions (`ProposedAction`) undergo deterministic verification against an Investment Policy Statement (IPS) by a Critic agent (`ReviewerVerdict`) before presenting an interactive approval card to the user.
- **End-to-End Traceability:** State, execution logs, and policy verdicts are persisted with immutable skill version and approval metadata.

---

## System Architecture

```text
 ┌─────────────────────────────────────────────────────────┐
 │               Vue 3 + TypeScript Frontend               │
 │    (Dashboard, Portfolio & Drift, Spending, Ingestion)  │
 └────────────────────────────┬────────────────────────────┘
                              │ HTTP / JSON
 ┌────────────────────────────▼────────────────────────────┐
 │                     Go Backend Host                     │
 │          (Static Asset Serving & API Gateway)           │
 └─────────────┬─────────────────────────────┬─────────────┘
               │                             │
    State & Ingestion                 Agent Dispatch
               │                             │
 ┌─────────────▼─────────────┐ ┌─────────────▼─────────────┐
 │    Google Cloud Store     │ │     Python Orchestrator   │
 │ ───────────────────────── │ │  (Gemini Enterprise ADK)  │
 │ • Firestore: IPS, State   │ │ ───────────────────────── │
 │ • BigQuery: Transactions  │ │ • Dynamic Skill Registry  │
 └───────────────────────────┘ │ • Reviewer / Critic Gate  │
                               └─────────────┬─────────────┘
                                             │ Paper Orders
                               ┌─────────────▼─────────────┐
                               │   Alpaca API (Sandbox)    │
                               └───────────────────────────┘
```
