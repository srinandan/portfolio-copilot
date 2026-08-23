# Portfolio Copilot

[![CI](https://github.com/srinandan/portfolio-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/srinandan/portfolio-copilot/actions/workflows/ci.yml)
[![OSV-Scanner](https://github.com/srinandan/portfolio-copilot/actions/workflows/osv-scanner.yml/badge.svg)](https://github.com/srinandan/portfolio-copilot/actions/workflows/osv-scanner.yml)
[![CodeQL](https://github.com/srinandan/portfolio-copilot/actions/workflows/codeql.yml/badge.svg)](https://github.com/srinandan/portfolio-copilot/actions/workflows/codeql.yml)
[![Release](https://img.shields.io/github/v/tag/srinandan/portfolio-copilot?label=version)](https://github.com/srinandan/portfolio-copilot/tags)
[![License](https://img.shields.io/github/license/srinandan/portfolio-copilot)](./LICENSE)
[![Go Version](https://img.shields.io/github/go-mod/go-version/srinandan/portfolio-copilot?filename=go.mod)](./go.mod)
[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](./orchestrator/pyproject.toml)
[![Node Version](https://img.shields.io/badge/node-20+-green.svg)](./frontend/package.json)

Portfolio Copilot is an experimental personal finance assistant built on Google Cloud's Gemini Enterprise Agent Platform. It uses dynamic runtime planning rather than static execution graphs: given a user objective, the root agent discovers currently available capabilities, drafts an execution plan, evaluates policy constraints, and requires explicit human approval before executing any trade actions.

> **Disclaimer:** This repository is an educational demo and reference implementation. It does not provide financial advice, and all trade execution is wired strictly to Alpaca's paper trading sandbox.

---

## Key Capabilities

- **Intent-Driven Planning:** Rather than relying on hardcoded workflows, the planner discovers registered skills at runtime and constructs each plan through a Retrieve → Plan → Resolve → Schedule pipeline — reading the user's intent to select which skills run, then deriving the execution order from each skill's self-describing manifest (`requires`/`produces`) instead of a fixed phase list. See [ADR-0022](docs/adr/0022-intent-driven-skill-planning.md).
- **Hot-Pluggable Capabilities:** Skills can be enabled or revoked mid-session; the planner recalculates its task graph on the subsequent step without restarting.
- **Human-in-the-Loop Trade Gate:** Proposed actions (`ProposedAction`) undergo deterministic verification against an Investment Policy Statement (IPS) by a Critic agent (`ReviewerVerdict`) before presenting an interactive approval card to the user.
- **End-to-End Traceability:** State, execution logs, and policy verdicts are persisted with immutable skill version and approval metadata.
- **Typed Document Ingestion:** Bank transaction CSVs and holdings/liabilities JSON snapshots load into BigQuery/Firestore, and IRS Form W-2 tax statements (PDF/PNG/JPEG) are parsed by Google Cloud Document AI — with the SSN masked — and persisted as `W2Document`, with 1-click sync to profile income. See [ADR-0026](docs/adr/0026-w2-document-ai-ingestion-and-profile-sync.md).
- **Advisory Equity Research:** For "should I buy/sell X?", two chained skills produce a standalone DCF valuation (`equity-research`, from free SEC EDGAR fundamentals + market quotes) and a suitability-adjusted `buy/add/hold/trim/avoid` recommendation against your IPS, holdings, and drift (`suitability`). Deterministic core, advisory only — it never drafts or executes a trade. See [ADR-0028](docs/adr/0028-equity-research-and-suitability-advisory-analysis.md).

---

## System Architecture

```text
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │                              Vue 3 + TypeScript Frontend                               │
 │         (Dashboard, Portfolio & Equity Analyzer, Spending, Profile & W-2 Hub)          │
 └───────────────────────────────────────────┬────────────────────────────────────────────┘
                                             │ HTTP / JSON & SSE Stream
 ┌───────────────────────────────────────────▼────────────────────────────────────────────┐
 │                                    Go Backend Host                                     │
 │                          (Static Asset Serving & API Gateway)                          │
 └─────────────┬─────────────────────────────┬─────────────────────────────┬──────────────┘
               │                             │                             │
     State & Ingestion Reads         Agent Dispatch (SSE)          W-2 Document Uploads
               │                             │                             │
 ┌─────────────▼─────────────┐ ┌─────────────▼─────────────┐ ┌─────────────▼────────────┐
 │     Google Cloud Store    │ │    Python Orchestrator    │ │  Google Cloud Document AI │
 │ ───────────────────────── │ │  (Vertex AI Agent Runtime)│ │ ───────────────────────── │
 │ • Firestore: IPS, Holdings│ │ ───────────────────────── │ │ • W-2 Income Extraction   │
 │   Profiles, W2s, Audit Log│ │ • Dynamic Intent Planner  │ │ • Automatic SSN Masking   │
 │ • BigQuery: Checking      │ │ • Reviewer / Critic Gate  │ └───────────────────────────┘
 │   Transactions (NL-to-SQL)│ │ • HITL Approval Gate      │
 └───────────────────────────┘ └───────┬───────┬───────┬───┘
                                       │       │       │
                  Skill Registry Reads │       │       │ SEC EDGAR XBRL & Quotes
                                       │       │       │ (DCF & Equity Fundamentals)
       ┌───────────────────────────────▼─┐     │       └───────────────┐
       │          Agent Registry         │     │                       │
       │ ─────────────────────────────── │     │         ┌─────────────▼───────────────┐
       │ • 8 Runtime Skills & Manifests  │     │         │      External Data Layer    │
       │ • Hot-Pluggable Dynamic Planning│     │         │ • SEC EDGAR (Company Facts) │
       └─────────────────────────────────┘     │         │ • Market Data / Quotes      │
                                               │         └─────────────────────────────┘
                            Sub-Agent Dispatch │ Paper Orders
                            (Interactions API) │
                                   ┌───────────▼──────────┐ ┌──────────────────────────┐
                                   │ Worker Managed Agent │ │        Alpaca API        │
                                   │ (Antigravity Sandbox)│ │     (Paper Trading)      │
                                   └──────────────────────┘ └──────────────────────────┘
```

For full architectural diagrams, component contracts, and design trade-offs, see the [Detailed Architecture Specification](docs/spec/02-architecture.md) and [Architecture Decision Records (ADRs)](docs/adr/).

## Get started

Setup instructions: [`install/`](install/).

## How to use it

Portfolio Copilot provides a standalone Vue 3 + TypeScript web interface connected to the backend server and Python orchestrator:

### First time: onboarding & profile (`/onboarding`, `/profile`)
Complete the guided onboarding interview, or configure the 6-tab **Profile & Policy Hub** (`/profile`): demographics, family dependents, career and retirement milestones, financial goals, risk tolerance, target allocation bands, liabilities, policy guardrails, and income & tax — upload an IRS Form W-2 (parsed via Google Cloud Document AI) with 1-click sync to your profile income. This atomically persists your active Investment Policy Statement (IPS), Liabilities snapshot, User Profile, and parsed W-2 statements (`W2Document`).

### Day to day: checking in (`/dashboard`, `/portfolio`, `/spending`, `/documents`)
- **Dashboard (`/`)**: Watch real-time agent planning, with a live progress checklist for each analysis stage (discovering skills, analyzing, reviewing), alongside net worth summaries and asset allocations.
- **Portfolio & Drift (`/portfolio`)**: Inspect current holdings alongside the live **Portfolio Drift Report**, comparing current allocations against your IPS target bands.
- **Spending Analysis (`/spending`)**: Review 30-day income, outflows, savings rate, reserve months, and dual-condition anomaly detections against checking transaction history.
- **Document Ingestion (`/documents`)**: Upload bank transaction CSVs (streamed directly into BigQuery with deduplication) and holdings/liabilities JSON snapshots into Firestore.

### When it wants to act: approving a trade (`<ApprovalCard />`)
If rebalancing or an investment trade is warranted:
1. **Action Drafting** drafts a specific trade proposal (`ProposedAction`).
2. **Reviewer & Critic** independently verifies the trade against your active IPS, holdings, and concentration limits, generating an itemized Policy Safety Checklist (`ReviewerVerdict`).
3. **Human-in-the-Loop Gate** presents an interactive card in the conversational UI where you can inspect rule results, edit trade quantities or rationales, and approve or reject before execution via Alpaca's paper trading API.

## Learn more

- **Component Documentation**:
  - [`orchestrator/README.md`](orchestrator/README.md): Python ADK root planner & dynamic planning workflow
  - [`frontend/README.md`](frontend/README.md): Standalone Vue 3 + TypeScript SPA & Go backend host
  - [`pkg/README.md`](pkg/README.md): Shared Go packages (contracts, Firestore repository, BigQuery runner)
  - [`scripts/README.md`](scripts/README.md): Provisioning, deployment, data loading, and admin scripts
- **Specifications & Architecture**: see [`docs/spec/`](docs/spec/) and [`docs/adr/`](docs/adr/).
- **Contributor / Coding-Agent Instructions**: see [`AGENTS.md`](AGENTS.md).

## Status

Foundation, orchestrator skills, Go backend server, and standalone Vue 3 frontend implemented. See [`docs/adr/`](docs/adr/) for the current state of each major decision.

## Contributing

Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for details on how to
contribute to this project.

## Support

This demo is *NOT* endorsed by Google or Google Cloud. The repo is
intended for educational/hobbyist use only.

## License

This project is licensed under the terms of the [LICENSE](./LICENSE) file.

