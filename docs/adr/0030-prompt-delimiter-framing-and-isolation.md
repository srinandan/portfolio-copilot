# ADR-0030: Prompt Delimiter Framing, Sanitization, and Policy Constraint Hardening

## Status

**Accepted.** Extends [ADR-0005](0005-managed-agents-hybrid-evaluation.md), [ADR-0007](0007-skill-content-via-input-not-mounting.md), [ADR-0014](0014-managed-agents-subagent-execution-layer.md), [ADR-0016](0016-deterministic-primitives-in-orchestrator.md), and [ADR-0025](0025-model-armor-floor-settings.md).

## Context

In Portfolio Copilot, worker Managed Agents execute dynamic skill turns (`spending-analysis`, `research`, `action-drafting`, `reviewer`, `goals-onboarding`) by receiving prompts compiled by the orchestrator (`_build_worker_prompt` in `dispatcher.py`).

Because the underlying worker base agent is stateless and only receives `node_input` as its user message, the prompt bundles:
1. Anti-exploration system operating rules.
2. The skill instructions (`SKILL.md` dynamically resolved from Agent Registry).
3. The expected output Pydantic schema.
4. The untrusted input data payload (which may contain raw user text, external Google Search snippets, SEC filings, or transaction notes).

When payloads are concatenated into plain unstructured text, adversarial text (e.g. `SKILL INSTRUCTIONS: Ignore previous rules...`) can simulate section headers to hijack the model's instruction frame (Direct and Indirect Prompt Injection). Furthermore, in conversational skills like `goals-onboarding`, adversarial or hallucinated inputs could produce malformed `InvestmentPolicyStatement` (IPS) constraints (e.g. zeroed concentration limits or non-normalized ticker symbols).

## Decision

1. **Structured XML Delimiter Blocks:**
   All worker Managed Agent prompts compiled by `_build_worker_prompt` are strictly partitioned into distinct XML-style blocks:
   - `<skill_instructions>`: The authoritative runtime skill contract from the registry.
   - `<output_schema>`: The target JSON schema definition.
   - `<untrusted_input>`: The external, preloaded data payload.

2. **Closing Tag Sanitization / Neutralization:**
   Any occurrence of `</untrusted_input>` within incoming payloads is escaped to `&lt;/untrusted_input&gt;` prior to prompt assembly, preventing user or external data from closing the untrusted context block.

3. **System Preamble Passive Data Invariant:**
   `_WORKER_SYSTEM_PREAMBLE` explicitly instructs the model that all content inside `<untrusted_input>` must be treated as passive data, and any instructions, commands, or system prompt overrides contained within it must be ignored.

4. **IPS Constraint Normalization & Bounds:**
   - `Constraints.excluded_tickers` is automatically sanitized by stripping whitespace and converting to uppercase (`strip().upper()`).
   - `Constraints.excluded_sectors` is automatically trimmed of extraneous whitespace.
   - `GoalsOnboardingResult.time_horizon_years` is bounded between 0 and 100 years.

## Consequences

- **Positive:** Establishes clear syntactic and semantic boundaries between system instructions and untrusted data payloads, mitigating prompt injection breakout.
- **Positive:** Normalizes policy constraints at ingestion time to ensure deterministic downstream rules in `reviewer` evaluate against clean, predictable identifiers.
- **Positive:** Retains complete statelessness between pipeline turns, preventing cross-skill prompt contamination.
- **Neutral:** Adds minor string-replacement overhead during prompt construction.
