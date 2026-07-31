# ADR-0009: Use ADK's native `ManagedAgent` class for Research, not hand-rolled Interactions API calls

## Status
Accepted. Refines the *mechanism* in
[ADR-0005](0005-managed-agents-hybrid-evaluation.md) and
[ADR-0007](0007-skill-content-via-input-not-mounting.md); doesn't change
either ADR's actual decisions.

## Context
ADR-0005 evaluated Managed Agents API as an execution layer for
Research, calling the Interactions API directly over REST. ADR-0007
resolved how to keep that live/registry-driven without native skill
mounting: the orchestrator resolves a skill's content from the Agent
Registry and passes it via the `input` field on each call.

ADK Python (`adk.dev/agents/managed-agents/`, supported since v2.4.0 —
this project's `orchestrator/pyproject.toml` already requires
`google-adk>=2.5.0`) provides a `ManagedAgent` class implementing the
standard `BaseAgent` contract. It connects to an existing managed agent
(e.g. Antigravity, referenced by `agent_id`) and handles the
Interactions API calls, streaming, and remote state tracking
(`previous_interaction_id`, sandbox `environment_id`) internally.
Critically, it drops directly into a `DynamicNode`/`Workflow` graph like
any other ADK node — no separate HTTP client code to write or test.

## Decision
Implement Research using ADK's `ManagedAgent`, constructed fresh each
planning cycle rather than once at startup:

```python
managed_research_agent = ManagedAgent(
    name="research",
    description=resolved_skill_content,  # from Agent Registry, this cycle
    agent_id="antigravity-preview-05-2026",
    environment={"type": "remote"},
    tools=[google_search],
)
```

Reconstructing the node each cycle (rather than a long-lived instance)
is what preserves ADR-0007's live-resolution property: `description` is
built from whatever the Agent Registry currently authorizes, so a
revoked Research skill is simply absent from the next planning cycle's
construction — no separate cache-invalidation logic needed, same as
every other registry-driven decision in this project.

**Tool scope: `google_search` only, no custom MCP server.**
`ManagedAgent` doesn't support MCP tools — only Google's server-side
built-ins (`google_search`, `code_execution`) — which conflicts with
ADR-0005's original per-turn *MCP* tool-override framing. Resolved by
checking what Research actually needs: Action Drafting already sources
pricing from Alpaca's own quote endpoint, so Research's real job is
sentiment/news context, which `google_search` covers natively. If a
future need genuinely requires a custom external data source
`ManagedAgent` can't reach, that's a signal to fall back to raw
Interactions API calls for that specific case — not a reason to avoid
`ManagedAgent` now for a need that doesn't yet exist.

## Consequences
- Less code to write and maintain — no hand-rolled HTTP client, auth,
  or streaming logic for the Interactions API
- Research's tool surface is simpler than originally envisioned
  (`google_search` only), which also makes its isolation property (see
  `skills/research/SKILL.md`) easier to verify — there's no custom MCP
  server configuration surface that could accidentally grow write access
- Unaffected by this ADR: ADR-0005's resolved execution boundary
  (trade execution never delegated, full stop), ADR-0008's Python pivot,
  and F5/F6 (already built, don't use `ManagedAgent` and don't need to)
- If Research's needs later exceed `google_search`, revisit — don't
  pre-build MCP support for a requirement that isn't real yet
