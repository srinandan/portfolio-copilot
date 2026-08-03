# ADR-0016: Deterministic primitives stay in the orchestrator (defer FastMCP)

## Status
**Accepted.** Complements [ADR-0014](0014-managed-agents-subagent-execution-layer.md).

## Context
Sub-agent execution involves both creative LLM reasoning (interviews, natural language summaries, rationale generation) and exact deterministic math (`calculate_drift`, `calculate_draft_action`, `calculate_savings_rate`, `calculate_reserve_months`, `calculate_risk_tolerance`, `is_anomalous`).

Two architectural approaches were evaluated for exposing these primitives:
1. **Separate Go / FastMCP Tool Server:** Deploying a dedicated MCP tool server so the Managed Agent calls primitives autonomously via MCP tool calls.
2. **In-Process Python Primitives:** Retaining existing Python functions under `orchestrator/src/orchestrator/primitives/`, pre-computing values in the orchestrator, and passing them to the Managed Agent.

The standalone MCP tool server approach was evaluated and rejected for the current phase: it introduces substantial operational complexity (a new microservice, deployment pipeline, IAM permissions, network latency, and transport rewriting from ADK `ManagedAgent` to raw Interactions API) for functionality already implemented and tested in Python.

## Decision
Deterministic math primitives remain Python functions inside the orchestrator under `orchestrator/src/orchestrator/primitives/`:
1. **Consolidation:** Move existing `skills/*/logic.py` files to `primitives/<name>.py` and their tests to `tests/primitives/`.
2. **Orchestrator-Managed Pre-computation:** The orchestrator invokes primitives directly during planning steps, packaging the computed outputs (e.g. `DriftReport`) into the input payload sent to the worker Managed Agent.
3. **Deferred FastMCP Evolution:** If autonomous primitive invocation by the LLM becomes a critical requirement in a future phase, primitives can be exposed via an in-process FastMCP server, accompanied by an ADR updating the transport layer.

## Consequences
- **Zero Infrastructure Overhead:** No additional Cloud Run microservices or external IAM boundaries required for math execution.
- **Preserved Test Invariants:** Existing comprehensive unit test suites for portfolio drift, rebalancing trim math, and anomaly formulas survive directly.
- **Known Tradeoff:** In this phase, the Managed Agent does not choose when to run primitives; the orchestrator handles pre-computation deterministically before invoking the agent.
