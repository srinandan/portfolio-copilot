# Portfolio Copilot

[![CI](https://github.com/srinandan/portfolio-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/srinandan/portfolio-copilot/actions/workflows/ci.yml)
[![OSV-Scanner](https://github.com/srinandan/portfolio-copilot/actions/workflows/osv-scanner.yml/badge.svg)](https://github.com/srinandan/portfolio-copilot/actions/workflows/osv-scanner.yml)
[![CodeQL](https://github.com/srinandan/portfolio-copilot/actions/workflows/codeql.yml/badge.svg)](https://github.com/srinandan/portfolio-copilot/actions/workflows/codeql.yml)
[![Release](https://img.shields.io/github/v/tag/srinandan/portfolio-copilot?label=version)](https://github.com/srinandan/portfolio-copilot/tags)
[![License](https://img.shields.io/github/license/srinandan/portfolio-copilot)](./LICENSE)
[![Go Version](https://img.shields.io/github/go-mod/go-version/srinandan/portfolio-copilot?filename=go.mod)](./go.mod)
[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](./orchestrator/pyproject.toml)
[![Node Version](https://img.shields.io/badge/node-20+-green.svg)](./frontend/package.json)

Portfolio Copilot is an experimental personal finance assistant built on Google Cloud's Gemini Enterprise Agent Platform. It demonstrates dynamic runtime planning over static execution graphs: given a user goal, the root agent discovers authorized skills from the Agent Registry, constructs an execution plan, enforces policy constraints with an independent critic, and requires explicit human approval before executing any paper trades.

> **Disclaimer:** This repository is an educational reference implementation. It does not provide financial advice, and all trade execution is wired strictly to Alpaca's paper trading sandbox.

---

## Key Capabilities

- **Intent-Driven Dynamic Planning:** Discovers registered skills at runtime and resolves dependencies dynamically (`requires`/`produces`) to build tailored execution plans, rather than running a rigid pipeline. See [ADR-0022](docs/adr/0022-intent-driven-skill-planning.md).
- **Hot-Pluggable Skills:** Supports adding or revoking skills mid-session; the planner recalculates its task graph on the next turn without restarting. See [ADR-0004](docs/adr/0004-dynamic-planning-over-fixed-pipeline.md).
- **Human-in-the-Loop Trade Governance:** Evaluates proposed actions against an Investment Policy Statement (IPS) using an independent Reviewer/Critic agent before rendering an interactive approval card for the user.
- **End-to-End Traceability:** Records all state transitions, skill execution logs, and reviewer verdicts with immutable skill versioning and approval metadata.
- **Document & Data Ingestion:** Streams bank transaction CSVs into BigQuery with deduplication, stores JSON snapshots in Firestore, and extracts W-2 income statements via Google Cloud Document AI (with automatic SSN masking). See [ADR-0026](docs/adr/0026-w2-document-ai-ingestion-and-profile-sync.md).
- **Dual-Layer Model Armor Guardrails:** Enforces Responsible AI, prompt-injection defense, and malicious-URI filtering across project services via Model Armor Floor Settings, coupled with an in-Runner per-request plugin screening for sensitive financial PII (SSN, routing, cards) using regional Cloud DLP inspect templates. See [ADR-0025](docs/adr/0025-model-armor-floor-settings.md) and [ADR-0032](docs/adr/0032-model-armor-runtime-plugin.md).
- **Advisory Equity Research:** Generates DCF valuations from SEC EDGAR fundamentals and produces suitability-adjusted allocation recommendations (`buy`/`add`/`hold`/`trim`/`avoid`) against your IPS. Advisory only—never executes trades automatically. See [ADR-0028](docs/adr/0028-equity-research-and-suitability-advisory-analysis.md).

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
 │ • BigQuery: Checking      │ │ • Model Armor Guardrails  │ └───────────────────────────┘
 │   Transactions (NL-to-SQL)│ │ • Reviewer / Critic Gate  │
 └───────────────────────────┘ │ • HITL Approval Gate      │
                               └───────┬───────┬───────┬───┘
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

---

## Getting Started

See [`install/`](install/) for prerequisites, local setup, and GCP deployment guides.

---

## User Journey

Portfolio Copilot pairs a standalone Vue 3 + TypeScript web interface with a Go backend gateway and Python orchestrator:

### 1. Onboarding & Policy Setup (`/onboarding`, `/profile`)
Establish your financial baseline and constraints:
- Complete the guided onboarding interview or configure the **Profile & Policy Hub** (`/profile`).
- Set retirement goals, risk tolerance, target asset allocation bands, liabilities, and policy guardrails.
- Upload IRS Form W-2 statements (parsed with Google Cloud Document AI, SSN automatically masked) and sync income to your profile with one click.
- Atomically saves your active Investment Policy Statement (IPS), user profile, liabilities, and tax documents in Firestore.

### 2. Day-to-Day Monitoring (`/dashboard`, `/portfolio`, `/spending`, `/documents`)
- **Dashboard (`/`)**: Watch real-time agent planning and execution stages (skill discovery, analysis, reviewer checks) alongside net worth and allocation summaries.
- **Portfolio & Drift (`/portfolio`)**: Track current holdings and monitor the live **Portfolio Drift Report** against your IPS target allocation bands.
- **Spending Analysis (`/spending`)**: Review 30-day cash flows, savings rates, emergency reserve runway, and automated spending anomaly detections.
- **Document Ingestion (`/documents`)**: Upload bank transaction CSVs (streamed directly to BigQuery with deduplication) and portfolio JSON snapshots.

### 3. Human-in-the-Loop Trade Approval (`<ApprovalCard />`)
When rebalancing or an investment trade is warranted:
1. **Action Drafting**: The agent drafts a specific trade proposal (`ProposedAction`).
2. **Reviewer & Critic**: An independent reviewer evaluates the trade against your active IPS, position limits, and drift, producing an itemized Policy Safety Checklist (`ReviewerVerdict`).
3. **Interactive Approval**: An approval card appears in the chat feed where you can inspect rule evaluations, modify trade quantities or rationales, and approve or reject before execution via Alpaca's paper trading API.

---

## Documentation & Repository Map

- **Components**:
  - [`orchestrator/README.md`](orchestrator/README.md): Python ADK root planner & dynamic planning engine
  - [`frontend/README.md`](frontend/README.md): Vue 3 TypeScript SPA & Go backend host
  - [`pkg/README.md`](pkg/README.md): Shared Go packages (domain contracts, Firestore store, BigQuery runner)
  - [`scripts/README.md`](scripts/README.md): Provisioning, deployment, data seeding, and admin scripts
- **Specifications & Decisions**: [`docs/spec/`](docs/spec/) and [`docs/adr/`](docs/adr/)
- **Contributor & Agent Guidelines**: [`AGENTS.md`](AGENTS.md)

---

## Contributing

Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for details on contributing.

## Support & Disclaimer

This demo is **not** an official Google or Google Cloud product. The repository is intended for educational and hobbyist reference only.

## License

This project is licensed under the terms of the [LICENSE](./LICENSE) file.

