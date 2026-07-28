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
  agent working on this repo. Read these before writing code or reviewing changes. They cover:
  - `code-coverage` — coverage targets and signal interpretation
  - `code-review` — two-axis review (Standards and Spec) using parallel sub-agents
  - `codebase-design` — module deepening, seam discipline, and interface design ("Design It Twice")
  - `concise-code` — code conciseness and avoiding premature abstraction
  - `unit-testing` — table-driven tests, fakes, and path coverage

## Repo map

```
docs/{spec,adr}/   Spec-driven design — read before changing architecture
skills/            Runtime skills (Agent Registry-facing, see above)
orchestrator/      Go — ADK root planner (DynamicNode)
gateway/           Go — API gateway (Cloud Run)
frontend/          TypeScript + Vue.js (Cloud Run)
infra/             Terraform
.agent/skills/     Engineering-practice skills (this repo's coding agent, see above)
```

## Build & test

Not yet implemented — filling in as each component is scaffolded.
Expected shape:

```bash
# orchestrator/, gateway/ (Go)
go build ./...
go test ./... -cover

# frontend/ (Vue + TS)
npm run build
npm run test -- --coverage
```

## Before writing code

1. Read the relevant engineering-practice skills in `.agent/skills/`:
   - `.agent/skills/concise-code/SKILL.md`, `.agent/skills/unit-testing/SKILL.md`, and `.agent/skills/code-coverage/SKILL.md` before writing or editing code.
   - `.agent/skills/code-review/SKILL.md` when reviewing code changes against repo standards and specs.
   - `.agent/skills/codebase-design/SKILL.md` when designing or refactoring module boundaries and interfaces.
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
