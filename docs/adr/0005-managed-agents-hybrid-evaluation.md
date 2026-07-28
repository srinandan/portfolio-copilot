# ADR-0005: Evaluating Managed Agents API as an execution layer

## Status
**Proposed / not yet committed.** Documented here specifically because
it's a live tradeoff with a genuinely open question, not settled fact.

## Context
Google's Managed Agents API (Pre-GA) lets you build an autonomous agent —
powered by the **Antigravity** harness — that reasons, plans, uses skills,
and executes code inside a managed sandbox. Two interfaces: the **Agents
API** (control plane — configure an agent's skills/tools/data sources) and
the **Interactions API** (data plane — talk to it at runtime).

Initial read was that this doesn't fit the project: the control-plane
configuration is set at agent-creation time, which looked incompatible
with "discover skills at runtime from the registry."

## Key enabler found on closer inspection
**Per-interaction tool overrides.** Any tools/MCP servers passed in a
specific Interactions API call completely override the agent's
preconfigured tools *for that one turn only*. This means the root
orchestrator can, on every call, compose a fresh MCP tool list from
whatever the Agent Registry currently authorizes, and Antigravity's
reasoning for that turn genuinely reflects live registry state — not a
config set once and left alone. This is a stronger mechanism for the
live-revocation demo than static agent-level config would have been.

## Proposed design
- **Root planner stays the Go/ADK orchestrator.** It queries the
  registry, decides what's authorized, and is the only thing that ever
  invokes Reviewer/Critic, human approval, and (see open question below)
  trade execution.
- **Plan + Research delegated to Antigravity via Interactions API**, with
  a read-only, registry-derived tool list attached per call.
- **HITL owned entirely by the orchestrator, between calls — not inside
  Antigravity.** Managed Agents has no native pause/resume primitive
  (unlike ADK's `RequestInput`). Resolution: the orchestrator doesn't ask
  Antigravity to pause mid-turn; it simply doesn't make the next
  Interactions API call until a human has approved. The turn boundary
  *is* the HITL gate.

## Constraints
- **Pre-GA.** Personal-use/demo is an accepted use case here.
- **Agent Registry recently shipped skill revisions** — directly usable
  for composing per-turn tool lists from specific authorized skill
  revisions. See [ADR-0006](0006-agent-registry-api-alignment.md) for
  the real API this project now aligns to (`agentregistry.googleapis.com`),
  which supersedes an earlier, less accurate reference to a different
  Google product ("Skill Registry" under Gemini Enterprise Agent
  Platform).

## Open question: where does trade execution happen?
Two options, not yet decided:

1. **Keep it in the orchestrator's own trusted Go code** (leaning this
   way). By approval time the action is fully specified — there's no
   reasoning benefit to routing it through an autonomous harness — and
   Google's own security guidance warns against granting an agent
   credentials beyond what a given step needs. A plain Alpaca API call
   from trusted code has less surface area than attaching a write-capable
   MCP tool to a Pre-GA sandbox.
2. **Delegate to Antigravity on the one approved call**, attaching the
   Alpaca MCP tool only for that turn via the same per-interaction
   override mechanism. Would let the demo show Antigravity completing the
   full plan→research→execute lifecycle inside one harness, if that
   narrative is worth the tradeoff.

## Consequences (if adopted)
- Antigravity never holds write credentials during Plan/Research,
  regardless of which way the open question resolves
- Real Chase/portfolio data must not be routed through the Managed Agents
  sandbox (Pre-GA terms); scope this integration to Research or synthetic
  data
- Adds a second execution pathway (ADK-direct skills vs. Interactions
  API-delegated skills) to reason about and document per-skill
