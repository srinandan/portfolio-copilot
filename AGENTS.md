# AGENTS.md

Instructions for any AI coding agent (Claude Code, Antigravity, or similar)
working in this repository. Human contributors should read this too.

## What this repo is

Portfolio Copilot — a personal finance/investment assistant demonstrating
registry-driven dynamic planning on the Gemini Enterprise Agent Platform.
Start with [`docs/spec/00-overview.md`](docs/spec/00-overview.md) for the
full picture before making non-trivial changes.

## Two different "skills" folders — don't confuse them

- **`/skills`** — runtime skills for the *deployed Portfolio Copilot agent
  itself*. These get registered with the Agent Registry and discovered by
  the root planner at runtime. Changing these changes what the product
  does. Any change here should trace back to `docs/spec/01-functional.md`.
- **`/.agent/skills`** — engineering-practice skills for *you*, the coding
  agent working on this repo. Read these before writing code. They cover
  code conciseness, unit testing, and coverage expectations.

## Repo map

```
docs/{spec,adr}/   Spec-driven design — read before changing architecture
skills/            Runtime skills (Agent Registry-facing, see above)
orchestrator/      Python — ADK root planner (DynamicNode), deployed to Agent Runtime
pkg/               Go — contracts, BigQuery, Firestore store
                    (library code for frontend/server; not consumed by orchestrator's Python)
frontend/          Vue 3 TypeScript SPA + Go backend server (Cloud Run)
scripts/           bash/gcloud/python and Makefiles for infra provisioning
.agent/skills/     Engineering-practice skills (this repo's coding agent, see above)
```

**Language note:** orchestrator is Python (Agent Runtime's deployment
contract is Python-only — see
[ADR-0008](docs/adr/0008-python-for-orchestrator.md)); frontend web host
and shared libraries are Go, since they are not agents.

## Build & test

```bash
# Full verification (lint + all test suites across Python, Go, and Vue)
make check

# Linting only (Python ruff + Go vet) — MUST pass before pushing any code
make lint       # or: uv run --project orchestrator ruff check . && go vet ./...

# orchestrator/ (Python)
cd orchestrator && uv run pytest --cov

# Go shared libraries & frontend server (Go)
go build ./...
go test ./... -cover

# frontend UI (Vue + TS)
cd frontend && npm run build && npm run test -- --coverage
```

## Branching & PR Workflow (Mandatory)

- **Never commit or push directly to `main`.** All changes must go through a feature/fix branch and a Pull Request.
- **For large changes / architectural features:** Always create a GitHub issue first outlining the scope, rationale, and design decisions, then create a linked Pull Request.
- **For smaller changes / bug fixes:** Directly create a feature branch and open a Pull Request.

## Pre-Push Checklist (Mandatory)

**Never push a branch or create/update a PR until all linters and tests pass locally.**
CI strictly runs `ruff check .` across the workspace and will reject any PR with lint errors.

Before running `git push`, always execute:
```bash
make check      # runs: make lint && make test
```
If only touching Python files, at a minimum verify:
```bash
uv run --project orchestrator ruff check .
cd orchestrator && uv run pytest
```

## Deployment — Always Use Makefile

**Always use the Makefile to deploy services.** Do not run ad-hoc `gcloud builds submit` or manual deployment commands directly.

```bash
# Deploy Full Stack (Both Orchestrator and Frontend)
make deploy

# Deploy Orchestrator to Vertex AI Agent Runtime
make deploy-orchestrator   # or: cd orchestrator && make deploy

# Deploy Frontend to Cloud Run
make deploy-frontend       # or: cd frontend && make deploy

# Provision Worker Managed Agent
make deploy-managed-agent

# Register Skills with Agent Registry
make register-skills

# Setup Agent Runtime IAM & Permissions
make setup-agent-engine

# End-to-End Environment Provisioning & Test Data
make setup-all
make load-testdata
```

## Before writing code

1. Read `.agent/skills/concise-code/SKILL.md`,
   `.agent/skills/unit-testing/SKILL.md`, and
   `.agent/skills/code-coverage/SKILL.md`. If you're touching anything
   Agent Runtime-related also read
   `.agent/skills/agent-runtime/SKILL.md`.
2. If the change affects what the system does, check it against
   `docs/spec/01-functional.md` first — update the spec, don't let code
   drift from it silently.
3. If the change is an architectural decision (new dependency, new data
   store, a tradeoff with real alternatives) — not just an implementation
   detail — add an ADR under `docs/adr/` rather than only leaving reasoning
   in a commit message or PR description.

## Conventions

- Conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`)
- No secrets, tokens, or credentials committed anywhere, including
  `scripts/` — use Secret Manager / environment injection
- Every skill in `/skills` must have a complete `SKILL.md` (no TODOs)
  before it's registered with the Agent Registry

## Talking to Agent Runtime (fka Agent Engine)

The only supported control-plane surface is the **Python `vertexai` SDK**
(`vertexai.Client(...).agent_engines`). The following `gcloud` command
groups **do not exist** — don't try them, and don't invent variants:

- `gcloud ai reasoning-engines …`
- `gcloud ai-platform …` (the entire group is dead)
- `gcloud agent-registry …` / `gcloud alpha agent-registry …`
- `gcloud alpha agents …`

For list / describe / query / delete / logs use
[`scripts/agent_engine_admin.py`](scripts/agent_engine_admin.py) — it
wraps the SDK behind a click CLI. Deploy/update is
[`scripts/deploy_agent_engine.py`](scripts/deploy_agent_engine.py). See
[`.agent/skills/agent-runtime/SKILL.md`](.agent/skills/agent-runtime/SKILL.md)
for the full playbook before troubleshooting.
