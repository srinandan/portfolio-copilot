# Portfolio Copilot

[![CI](https://github.com/srinandan/portfolio-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/srinandan/portfolio-copilot/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/srinandan/portfolio-copilot)](./LICENSE)
[![Go Version](https://img.shields.io/github/go-mod/go-version/srinandan/portfolio-copilot?filename=go.mod)](./go.mod)
[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](./orchestrator/pyproject.toml)
[![Node Version](https://img.shields.io/badge/node-20+-green.svg)](./frontend/package.json)
[![CodeQL](https://github.com/srinandan/portfolio-copilot/actions/workflows/codeql.yml/badge.svg)](https://github.com/srinandan/portfolio-copilot/actions/workflows/codeql.yml)

Portfolio Copilot is a personal finance and investing assistant that
plans its own next move instead of following a fixed script. A single
agent reads your goal, checks which capabilities it's currently allowed
to use, and composes a plan at runtime — pulling research, checking your
portfolio, and drafting a trade when warranted. No trade executes without
your approval, and every action is traceable to the capability that
produced it.

## Why try it

- **It plans, it doesn't run a script.** The agent decides what to check
  and do at request time, rather than executing a hardcoded pipeline.
- **Capabilities can be revoked live, mid-conversation.** Revoke a skill
  and the agent adapts on its next planning step — no restart, no error.
- **No trade executes without your approval.** Trades are drafted,
  checked against your stated investment policy, and executed only after
  you approve.
- **Governance is real, not a slide.** Every action is traceable to the
  exact skill, version, and approval that authorized it.

This is a personal project and demo built on Google Cloud's Gemini
Enterprise Agent Platform. It is not a product, not investment advice,
and not connected to a real brokerage (trades run through Alpaca's paper
trading API).

## Get started

Setup instructions: [`install/`](install/).

## How to use it

Portfolio Copilot provides a standalone Vue 3 + TypeScript web interface connected to the backend server and Python orchestrator:

### First time: onboarding & profile (`/onboarding`, `/profile`)
Complete the guided onboarding interview, or configure the 5-tab **Profile & Policy Hub** (`/profile`): demographics, family dependents, career and retirement milestones, financial goals, risk tolerance, target allocation bands, liabilities, and policy guardrails. This atomically persists your active Investment Policy Statement (IPS), Liabilities snapshot, and User Profile.

### Day to day: checking in (`/dashboard`, `/portfolio`, `/spending`, `/documents`)
- **Dashboard (`/`)**: Watch real-time agent planning, with a live progress checklist for each analysis stage (discovering skills, analyzing, reviewing), alongside net worth summaries and asset allocations.
- **Portfolio & Drift (`/portfolio`)**: Inspect current holdings alongside the live **Portfolio Drift Report**, comparing current allocations against your IPS target bands.
- **Spending Analysis (`/spending`)**: Review 30-day income, outflows, savings rate, reserve months, and dual-condition anomaly detections against Chase transaction history.
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
