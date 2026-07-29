# ADR-0001: Go over Python for the agent implementation

## Status
**Superseded by [ADR-0008](0008-python-for-orchestrator.md).** The
capability-parity verification below was accurate for what it tested —
it just tested the wrong thing. Agent Runtime's deployment contract
turned out to be Python-only, which capability parity on ADK features
doesn't help with. Preserved here as the historical record, not deleted.

## Context
ADK 2.0 supports both Python and Go. Python is the reference
implementation and historically gets new capabilities first. Go was
preferred for performance, but that preference was only worth acting on if
Go had no material capability gap for what this project actually needs.

## Decision
Use Go for both the orchestrator and the agents.

## Verification (before committing)
Checked official ADK docs directly rather than assuming parity:

- **Dynamic workflows** (the core requirement — `DynamicNode` with
  programmatic control flow): supported in Python v2.0.0 **and** Go
  v2.0.0. Full parity, not a lagging feature.
- **Memory Bank**: Go's `memory` package implements the same
  `MemoryService` interface as Python, including the Vertex AI-backed
  service. Mature (Go since v0.1.0).
- **Agent Engine deployment**: Go supported since v1.2.0 via
  `adkgo deploy agentengine`.
- **A2A**: exposing and consuming quickstarts exist for Go, alongside
  Python and Java.
- **Convenience SDK for Managed Agents/Interactions API**: Python-only as
  of this writing (no Go tab in Google's docs). Not a blocker — the API is
  REST-first by design, and the orchestrator was always going to call it
  as a plain HTTP client rather than pull in a framework dependency.

## Consequences
- No capability gap found on anything load-bearing for this design
- Go's concurrency model is a good fit for the Cloud Run service topology
- Managed Agents/Interactions API calls are hand-rolled HTTP rather than
  SDK-wrapped, which is a minor implementation cost, not a design one
