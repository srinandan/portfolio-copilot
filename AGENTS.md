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
gateway/           Go — API gateway (Cloud Run) — not an agent, unaffected by orchestrator's language
frontend/          TypeScript + Vue.js (Cloud Run)
infra/             Terraform
.agent/skills/     Engineering-practice skills (this repo's coding agent, see above)
```

**Language note:** orchestrator is Python (Agent Runtime's deployment
contract is Python-only — see
[ADR-0008](docs/adr/0008-python-for-orchestrator.md)); gateway is Go,
since it isn't an agent and never touches that contract. Don't assume
one language across the whole repo.

## Build & test

Not yet implemented — filling in as each component is scaffolded.
Expected shape:

```bash
# orchestrator/ (Python)
pip install -e ".[dev]"
pytest --cov

# gateway/ (Go)
go build ./...
go test ./... -cover

# frontend/ (Vue + TS)
npm run build
npm run test -- --coverage
```

## Before writing code

1. Read `.agent/skills/concise-code/SKILL.md`,
   `.agent/skills/unit-testing/SKILL.md`, and
   `.agent/skills/code-coverage/SKILL.md`.
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
  `infra/` — use Secret Manager / environment injection
- Every skill in `/skills` must have a complete `SKILL.md` (no TODOs)
  before it's registered with the Agent Registry
