# ADR-0014: Managed Agents as the sub-agent execution layer

## Status
**Accepted.** Supersedes [ADR-0005](0005-managed-agents-hybrid-evaluation.md) by expanding Managed Agents execution to all sub-agents, and extends [ADR-0007](0007-skill-content-via-input-not-mounting.md) and [ADR-0009](0009-managed-agent-native-class.md). Preserves the core principle that trade execution and HITL state management remain strictly inside orchestrator code.

## Context
ADR-0005 originally evaluated Google Cloud Managed Agents (Antigravity harness) strictly for Research on safety grounds. In this architecture, all sub-agents (`goals-onboarding`, `portfolio-analysis`, `research`, `action-drafting`, `spending-analysis`, and `reviewer`) benefit from autonomous reasoning, natural language interview execution, and rationale generation.

Rather than provisioning separate static Managed Agents per skill, a single "worker" Managed Agent (`portfolio-copilot-worker`) is provisioned per environment. At runtime, the orchestrator queries the Agent Registry to resolve authorized `SKILL.md` content and provides this as the `description` per Interaction.

## Decision
All sub-agents execute as Managed Agents invoked by the root orchestrator via ADK's native `ManagedAgent` class:
1. **Single Worker Agent:** A single worker Managed Agent resource is provisioned per environment, referenced by `MANAGED_AGENT_ID`.
2. **Per-Interaction Identity:** On each skill execution turn, the orchestrator sets `description=resolved_skill_content`, attaching relevant tools (such as `google_search` for research) and specifying a Pydantic `output_schema`.
3. **Deterministic Math Stays in Orchestrator:** Pure math calculations (`calculate_drift`, `calculate_draft_action`, `calculate_savings_rate`, etc.) remain Python functions inside the orchestrator (see [ADR-0016](0016-deterministic-primitives-in-orchestrator.md)). The orchestrator pre-fetches state, pre-computes numeric results, and passes them as structured context to the Managed Agent.
4. **State Writes & HITL Remain Outside Sandbox:** The Managed Agent produces structured outputs and rationales. All state mutations (Firestore IPS writes, ProposedAction creation, audit log appending) and external execution (Alpaca API calls) remain strictly owned and executed by the trusted orchestrator.

## Consequences
- **Uniform Execution Layer:** The orchestrator dispatches every skill through a single generic Managed Agent code path rather than maintaining bespoke sub-agent node runners.
- **Dynamic Revocation:** Revoking a skill in the Agent Registry immediately removes it from execution without requiring deleting or re-provisioning Managed Agent resources.
- **Formatter / Reasoner Role for Deterministic Skills:** For portfolio-analysis and action-drafting, the Managed Agent reasons over orchestrator-precomputed values and writes human-readable rationales and structured reports.
- **Trust Boundary Integrity:** The Antigravity sandbox never holds database write credentials or broker trade execution secrets.
