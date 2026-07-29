# ADR-0008: Python for the orchestrator and skill logic — supersedes ADR-0001

## Status
Accepted. Supersedes [ADR-0001](0001-go-over-python-for-agents.md).

## Context
ADR-0001 chose Go for the agent implementation after verifying feature
parity with Python on the specific ADK 2.0 capabilities this project
needs: dynamic workflows, Memory Bank, Agent Engine deployment, and A2A.
That verification was real and each claim was checked against official
docs at the time.

While scoping Dockerfiles for deployment, `docs.cloud.google.com/
gemini-enterprise-agent-platform/scale/runtime/deploy-an-agent` states
plainly: **"Agent Runtime deployment only supports Python."** The
custom-agent contract (`create-a-custom-agent`) is built entirely around
a Python class — `__init__`/`set_up()`/`query()`/`stream_query()`, with
the constructor's result required to be pickle-able. No documented path
exists for a non-Python container to satisfy that contract, including
via the Dockerfile/container-image deployment methods, which are framed
as alternate *packaging* mechanisms for the same class-based contract,
not a generic escape hatch.

This directly contradicts ADR-0001's premise. A feature that tests as
available but can't actually be deployed isn't available.

## Decision
The orchestrator, and any skill logic that runs as part of its
reasoning/planning, is implemented in **Python**, deployed to Agent
Runtime using the documented custom-agent class contract (or the Agents
API path where applicable, per ADR-0005/0007).

**Scope, precisely — this is not "rewrite everything in Python":**
- **Orchestrator (agent logic): Python.** This is what the constraint
  actually applies to.
- **Gateway: stays Go.** It is not an agent — it never gets deployed
  through Agent Runtime's contract. It's an API/auth/streaming layer
  that calls the orchestrator's API from outside. Nothing about the
  Python-only constraint touches it.
- **Frontend: unaffected.** Already TypeScript/Vue, already Cloud Run,
  never touched Agent Runtime.

## An upside worth naming, not just a consolation
Agent Runtime's own docs recommend Pydantic (or `TypedDict`) for typing
an agent's inputs/outputs. Pydantic models can validate directly against
the same `schemas/*.schema.json` files already in this repo more
natively than the hand-rolled `Validate()` methods the Go
implementation used — which is directly relevant given the sanity check
on F1–F4 found a real bug where Go's Firestore serialization silently
diverged from the JSON-schema-documented field names. A Pydantic model
used consistently for both validation and serialization doesn't have
that failure mode, because there's only one representation instead of
two (a `json.Marshal` shape and a separate Firestore struct-mapping
shape) that can drift apart.

## Consequence worth flagging explicitly: Firestore access now exists in two languages
Per [ADR-0003](0003-standalone-ui-not-agentspace.md), the gateway
already does some direct Firestore access on its own (the approval-write
path, fan-out reads for charts) — that was a deliberate design decision
made independently of language. With the orchestrator now in Python:
- **Gateway (Go)** keeps its own Firestore client for what it already
  owns directly (approval-write path, fan-out reads)
- **Orchestrator (Python)** needs its own Firestore client for what
  skills read/write during execution (IPS, holdings, liabilities)

This is genuine duplication of client-level code across two languages,
not a design flaw introduced by this ADR — it's the honest cost of
ADR-0003's gateway-does-some-direct-access decision now that the two
services don't share a language. Both sides validate against the same
`schemas/*.schema.json` regardless, so the contracts themselves don't
diverge even though the client code implementing them does.

## What this does not change
- Every ADR's reasoning about *what* the system does (0002 through
  0007) is untouched — data layer split, standalone UI, dynamic
  planning, Managed Agents evaluation, Agent Registry alignment, and
  skill-content-via-input all hold regardless of orchestrator language
- All five `SKILL.md` specs, `docs/spec/03-contracts.md`, and the six
  JSON schemas are language-agnostic and require no changes
- ADR-0001 is preserved, not deleted — its verification work was
  accurate for what it tested; it just tested the wrong thing
  (capability parity) instead of the thing that turned out to matter
  (deployability)

## Follow-up work this creates (not resolved by this ADR itself)
- Port `orchestrator/contracts/*.go` to Pydantic models
- Port the Agent Registry client to Python (once restored per the F1–F4
  sanity check — it doesn't currently exist on `main` regardless of
  language)
- Port the orchestrator-side Firestore CRUD logic to Python, most
  importantly the IPS versioning transaction
- Update `.agent/skills/unit-testing` and `code-coverage` with Python
  conventions alongside the existing Go ones (gateway still needs Go
  guidance)
- Update CI to run a Python job for the orchestrator, Go job for the
  gateway only
- Decide how to handle the now-Go-scoped F1, F4, F5 GitHub issues —
  supersede and reopen as Python-scoped, or amend in place
