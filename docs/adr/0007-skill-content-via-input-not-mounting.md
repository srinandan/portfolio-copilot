# ADR-0007: Resolve skill content via the orchestrator, pass as per-call input — not sandbox mounting

## Status
Accepted. Mechanism refined by
[ADR-0009](0009-managed-agent-native-class.md): the *principle* here
(skill content resolved fresh from Agent Registry, never statically
mounted) is unchanged, but for Research specifically, "pass via the
Interactions API's `input` field" became "construct a fresh
`ManagedAgent(description=...)` node each cycle" once ADK's native
wrapper became the implementation path.

## Context
Managed Agents API's skill-mounting mechanism (`base_environment.sources`,
available both at agent creation and as a per-interaction override)
currently supports two source types: `skill_registry` (a different
Google product — the Gemini Enterprise Agent Platform's "Skill
Registry," not the real Agent Registry this project aligns to per
[ADR-0006](0006-agent-registry-api-alignment.md)) and `gcs`.

Neither is acceptable as-is:
- `skill_registry` couples the design to the wrong product
- `gcs` requires a bucket kept in sync with the real Agent Registry,
  reintroducing a staleness window that the per-turn, registry-driven
  design (ADR-0005) was specifically built to avoid

## Decision
Don't use the sandbox skill-mounting mechanism at all. Instead:

1. The orchestrator already knows which skills are currently authorized
   (from its own Agent Registry query)
2. For each one it wants Antigravity to use that turn, it reads that
   skill's current content directly
   (`projects.locations.skills.revisions.get` — a plain read against the
   real Agent Registry, available today)
3. It folds that content into the **`input` field of that specific
   Interactions API call** — not the agent's static `system_instruction`,
   which is set once at creation and would go stale — alongside the
   per-turn MCP tool list from ADR-0005
4. Repeated every call. A revoked skill (`targetState:
   TARGET_STATE_DISABLED`) simply stops being fetched in step 1, so the
   very next call already reflects it — no separate sync step, no cache
   invalidation logic

## Consequences
- Works today, with zero dependency on Managed Agents adding native
  Agent Registry support
- Genuinely live — every call reflects current registry state, same
  property the MCP tool-override mechanism already has
- **Known limitation, accepted:** this only carries the SKILL.md
  instruction text. `scripts/`, `references/`, and `assets/`
  subdirectories aren't real files in the sandbox this way — nothing is
  actually mounted. None of this project's current skills use those
  subdirectories, so this isn't a live blocker, but it would force the
  mounting question back open if a future skill needs an executable
  script.
- **`inline` source type checked and ruled out.** It appears in general
  Gemini API documentation, but is confirmed **not available** on
  Managed Agents as offered through GCP (Gemini Enterprise Agent
  Platform) — that surface only supports `skill_registry` and `gcs`, per
  the Context section above. This isn't a gap to keep re-checking; it's
  resolved. Passing skill content via `input` (or another
  request-scoped field) is the only viable live-resolution path on the
  GCP surface today, which makes this ADR's decision the settled answer
  for this project, not a stand-in for a better option pending
  verification.

