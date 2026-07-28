---
name: unit-testing
version: 0.1.0
audience: coding-agent
---

# Unit testing

Applies to all code in this repo. Every new exported function, HTTP
handler, or Vue component with logic beyond pure markup needs a test
before the PR is considered done — not added later.

## Go (`orchestrator/`, `gateway/`)

- Table-driven tests, co-located as `*_test.go` next to the code under
  test.
- Test behavior, not implementation — assert on outputs/side effects, not
  on internal call sequences, unless the sequence itself is the contract
  (e.g. "Reviewer must run before execution").
- External calls (Alpaca, BigQuery, Firestore, Agent Registry, Interactions
  API) go behind small interfaces at the point of use, with fakes for
  tests — never hit real external services in unit tests.
- Minimum per function: one golden-path case, one error-path case. Add
  edge cases (empty input, boundary values) where the domain has them —
  e.g. zero-quantity trades, expired skill TTL.
- For the Reviewer/Critic and HITL gate specifically: test the *rejection*
  paths as thoroughly as the approval path. This is the governance
  surface — undertested rejection logic defeats the point of the demo.

## TypeScript / Vue (`frontend/`)

- Vitest + Testing Library. Test user-visible behavior (what renders,
  what a click does), not component internals or implementation details.
- Every component that renders conditionally (e.g. the approval card's
  approve/edit/reject states) needs a test per state.

## What NOT to do

- Don't write a test just to move a coverage number — see
  `code-coverage/SKILL.md`.
- Don't mock what you don't own carelessly — if a fake for an external
  API drifts from its real behavior, the test suite gives false
  confidence. Keep fakes minimal and reviewed when the real API's
  contract changes.
- Don't test framework code (e.g. that a Go struct's field assignment
  works) — test your logic.
