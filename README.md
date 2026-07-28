# Portfolio Copilot

A personal finance/investment assistant, built as a demo of Gemini Enterprise
Agent Platform capabilities — specifically **registry-driven dynamic
planning**: a single root agent that discovers and composes its own plan at
runtime from whatever skills it's currently authorized to use, rather than a
hardcoded multi-agent pipeline.

This is a personal-use demo project, not a production system.

## Start here

- [`docs/spec/00-overview.md`](docs/spec/00-overview.md) — vision, demo narrative, what "done" looks like
- [`docs/spec/01-functional.md`](docs/spec/01-functional.md) — what the system does
- [`docs/spec/02-architecture.md`](docs/spec/02-architecture.md) — tech stack and deployment topology
- [`docs/adr/`](docs/adr/) — architecture decisions, with alternatives considered

## Repo layout

```
portfolio-copilot/
├── AGENTS.md            Instructions for any coding agent working in this repo
├── docs/{spec,adr}/     Spec-driven design docs
├── orchestrator/        Go, ADK root planner (DynamicNode)
├── skills/              Runtime skills for the deployed agent (Agent Registry-facing)
├── .agent/skills/       Engineering-practice skills for coding agents (this repo)
├── gateway/             Go API gateway (Cloud Run)
├── frontend/            TypeScript + Vue.js (Cloud Run)
└── infra/               Terraform
```

**Note:** `skills/` and `.agent/skills/` are not the same thing. `skills/`
defines what the *product* can do (registered with the Agent Registry,
discovered by the root planner at runtime). `.agent/skills/` defines how
*code in this repo* should be written (concise, tested, covered) — see
[`AGENTS.md`](AGENTS.md).

## Status

Architecture and functional spec drafted. Implementation not yet started.
See ADRs for decisions still open (notably ADR-0005, the Managed Agents
execute-step question).
