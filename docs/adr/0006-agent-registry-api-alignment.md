# ADR-0006: Align to the real Agent Registry API

## Status
Accepted

## Context
Earlier docs in this project (functional spec, ADR-0005) referenced "the
Agent Registry" somewhat abstractly, and at one point cited a different
Google product — the Gemini Enterprise Agent Platform's "Skill Registry"
(`skills/{name}/skill_versions/{version}`) — as the closest analog to
this project's governance design.

That reference was corrected after reviewing the actual, dedicated
**Agent Registry** product (`docs.cloud.google.com/agent-registry`, API
host `agentregistry.googleapis.com`) — a standalone registry covering
agents, skills, MCP servers, services, and bindings. This is the
authoritative product this project now aligns to.

## Decision
Portfolio Copilot's skills are modeled against the real Agent Registry
`Skill` resource, not a hand-waved abstraction. Specifically:

### Resource naming
- Format: `projects/{project}/locations/{location}/skills/{skill}`
- Self-registered skills (no verified publisher namespace) are
  automatically namespaced under the `private-` prefix — e.g. a skill
  created with ID `goals-onboarding` is registered as
  `private-goals-onboarding`. Every skill's `SKILL.md` "Registered as"
  line reflects this.
- `type: SIMPLE` for all of this project's skills (leaf executable
  skills; `COMPOSITE`/bundle is a different, unused resource shape).

### Revisions, not "versions"
The correct term in this API is **skill revision**
(`projects.locations.skills.revisions`), not "skill version." A skill
has a `defaultRevision` — a floating pointer to the revision currently
served — and can hold multiple revisions simultaneously. All prior
references to `skill_versions/{version}` in this repo's docs were
terminology errors from the earlier, wrong product reference; corrected
throughout.

### Lifecycle states — the actual revocation mechanism
The `Skill` resource has two lifecycle enums:
- `state` (system-managed, output-only): `STATE_CREATING`,
  `STATE_DRAFT`, `STATE_ACTIVE`, `STATE_DISABLED`, `STATE_DEPRECATED`,
  `STATE_DECOMMISSIONED`, `STATE_DELETING`
- `targetState` (user-managed, what you set): `TARGET_STATE_DRAFT`,
  `TARGET_STATE_ACTIVE`, `TARGET_STATE_DISABLED`,
  `TARGET_STATE_DEPRECATED`, `TARGET_STATE_DECOMMISSIONED`

**This replaces the earlier vague "TTL/revoke via the registry" language
in the functional spec's demo scenarios with a concrete API call**: the
live-revocation demo is a `PATCH` setting `targetState` to
`TARGET_STATE_DISABLED` (or moving `defaultRevision` to point elsewhere),
and the root planner's next registry query genuinely reflects that
change — not a simulated revocation.

### SKILL.md frontmatter — Agent Skills Specification compliance
Agent Registry's ingestion validation requires SKILL.md to have valid
YAML frontmatter per the [Agent Skills Specification](https://agentskills.io/specification).
Reviewing this project's SKILL.md files against the spec surfaced two
real gaps, now fixed across all eight SKILL.md files (five runtime
skills, three `.agent/skills/` engineering-practice skills):

1. **Missing `description` field.** The spec requires frontmatter
   `description` (1–1024 chars) stating both *what* the skill does and
   *when* to use it. This project previously only had a "Purpose"
   section in the Markdown body, which the spec doesn't recognize as a
   substitute.
2. **Custom fields at the wrong level.** `version` and `status`/`audience`
   were top-level frontmatter keys. The spec's convention nests
   non-standard fields under a `metadata:` map instead.

### Ingestion constraints (for future registration work)
- Max compressed ZIP: 500 KB; max uncompressed: 10 MB; max 1 MB per file;
  max directory nesting: 8 levels. This project's SKILL.md files are
  plain text, far under any of these limits.

## Consequences
- Every SKILL.md's "Registry metadata" section now shows the correct
  `private-{skill}` resource name and calls the versioning concept
  "revision," not "version"
- The live-revocation demo has a concrete, real API call behind it
  (`targetState` PATCH) rather than an abstract "revoke it somehow"
- Agent Registry is itself Preview/Pre-GA — same posture as Managed
  Agents API (ADR-0005): acceptable for this personal demo, not a
  production dependency
- Anywhere else in this repo that still says "Skill Registry" or
  `skill_versions` is a leftover from the earlier wrong reference and
  should be corrected on sight
