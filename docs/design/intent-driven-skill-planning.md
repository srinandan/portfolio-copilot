# Design: Intent-driven skill planning

Companion to [ADR-0022](../adr/0022-intent-driven-skill-planning.md). The ADR
records *the decision*; this document records *how we build it* — the manifest
schema, the planner contract, worked examples for the current six skills, and
the phase-by-phase task breakdown.

## 1. Problem recap

Today `root_planner` selects skills by intersecting
`list_authorized_skills()` with a hardcoded whitelist of six `SKILL_PLANS`,
then runs **all** of them in a fixed three-phase order. It never reads the
user's intent, and adding a skill requires editing the orchestrator. We want
plan construction to be **intent-driven** and **skill-additive**: a new skill
plus its manifest should be routable with no orchestrator change.

The pipeline becomes four stages:

```
prompt ─▶ RETRIEVE ──▶ PLAN ──▶ RESOLVE ──▶ SCHEDULE ──▶ EXECUTE
          candidates    leaves   +prereqs    layers        (existing
          (semantic)    (policy)  +gates      (topo)         dispatch)
```

Two knowledge sources feed it, kept strictly separate:

| Knowledge | Lives in | Example | Owned by |
|-----------|----------|---------|----------|
| **Structure** (dependencies, outputs) | the skill's **manifest** | `action-drafting requires drift_report` | skill author |
| **Policy** (intent → include/exclude) | the **planner skill** | "trade-intent prompts include the trade path" | planner owner |

## 2. Skill manifest schema

Machine-readable metadata shipped with each skill (SKILL.md front-matter or a
sibling `manifest.json` in the registry revision zip — see open question).

```yaml
# manifest for `private-action-drafting`
id: action-drafting            # short id (no `private-` prefix)
summary: >                     # one line; embedded for semantic search
  Drafts a single compliant rebalancing trade from portfolio drift and policy.
applies_when: >                # natural-language trigger for the planner/search
  The user asks to rebalance, trade, buy, sell, or act on portfolio drift.
requires: [drift_report, active_ips, holdings]   # artifacts consumed
optional: [research_briefs]                       # used if present, not required
produces: [proposed_action]                       # artifacts emitted
parallelizable: false          # may run concurrently with same-layer peers?
mandatory_if: null             # compliance rule; see reviewer example
default: false                 # is this the cold-start floor skill?
```

| Field | Type | Purpose |
|-------|------|---------|
| `id` | string | Short skill id; matches registry `private-<id>`. |
| `summary` | string | One-liner; the primary text embedded for semantic retrieval. |
| `applies_when` | string | Intent trigger used by the planner (and search). |
| `requires` | `[artifact]` | Inputs that must exist; drive prerequisite resolution. |
| `optional` | `[artifact]` | Inputs consumed if available; do **not** pull in prerequisites. |
| `produces` | `[artifact]` | Outputs; the other half of the dependency graph. |
| `parallelizable` | bool | Whether it may share a schedule layer. |
| `mandatory_if` | expr \| null | Structural compliance trigger (e.g. `proposed_action exists`). |
| `default` | bool | Marks the cold-start floor skill. |

**Artifacts** are the vocabulary that links skills. Initial set, drawn from
the existing contracts and preloaders:
`spending_report`, `active_ips`, `drift_report`, `holdings`,
`research_question`, `research_briefs`, `proposed_action`,
`reviewer_verdict`, `hitl_decision`, `execution_result`.

## 3. Worked manifests for the current six skills

These make the dependency DAG concrete and must reproduce today's behaviour
in Phase 2 (see §7).

| Skill | requires | optional | produces | mandatory_if | parallelizable |
|-------|----------|----------|----------|--------------|----------------|
| `spending-analysis` | — (facts preloaded) | — | `spending_report` | — | yes |
| `goals-onboarding` | — | — | `active_ips` | — | yes |
| `portfolio-analysis` | `active_ips`, `holdings` | — | `drift_report` | — | yes |
| `research` | `research_question` | — | `research_briefs` | — | yes |
| `action-drafting` | `drift_report`, `active_ips`, `holdings` | `research_briefs` | `proposed_action` | — | no |
| `reviewer` | `proposed_action`, `active_ips`, `holdings` | — | `reviewer_verdict` | `proposed_action exists` | no |

Gates (deterministic orchestrator nodes, **not** skills — kept as-is):

| Gate | triggered by | produces |
|------|--------------|----------|
| HITL approval (`hitl_approval_gate`) | `proposed_action` drafted | `hitl_decision` |
| Execution (`execution_gate`) | `hitl_decision == approved` | `execution_result` |

The DAG these edges describe:

```
spending-analysis ─┐
goals-onboarding ──┤ (independent)      research ─┐
                   │                              │
   active_ips + holdings                          │
        │                                         │
   portfolio-analysis ── drift_report ── action-drafting ◀─ research_briefs
                                              │
                                        proposed_action
                                              │
                                          reviewer ── reviewer_verdict
                                              │
                                    HITL gate ── execution gate
```

Topologically sorting *this* graph reproduces the current three phases
automatically — which is the Phase 2 correctness test.

## 4. The planner skill

### 4.1 Contract

```jsonc
// INPUT (built in-process by the orchestrator)
{
  "prompt": "should I trim my tech exposure?",
  "context": {
    "has_active_ips": true,
    "has_recent_drift_report": false,
    "requested_trade": null
  },
  "candidates": [            // from RETRIEVE; list-all in v1, semantic later
    { "id": "portfolio-analysis", "summary": "...", "applies_when": "..." },
    { "id": "research",           "summary": "...", "applies_when": "..." }
  ]
}

// OUTPUT
{
  "leaves": ["portfolio-analysis", "action-drafting"],
  "rationale": "Trade intent on existing holdings; needs current drift.",
  "policy_applied": ["default-floor", "trade-intent-include"]
}
```

`leaves` are **intent leaves only** — the user-facing goals. Prerequisites
(e.g. `action-drafting` pulling in `portfolio-analysis`) and gates are added
later by the deterministic resolver, never by the planner.

### 4.2 Policy is expressed both ways (decision 3 = "both")

The planner skill carries a natural-language prompt **and** a structured
policy block. v1 evaluates only the structured block; the prompt is used once
the LLM prune is enabled.

```yaml
# planner skill — structured policy block
default_floor: spending-analysis      # always contributed as a baseline
rules:
  - name: trade-intent-include
    when: "context.requested_trade != null"
    include: [action-drafting]
  - name: read-only-exclude
    when: "intent == 'informational'"
    exclude: [action-drafting]
  - name: onboarding-once
    when: "context.has_active_ips == true"
    exclude: [goals-onboarding]
```

```
# planner skill — natural-language prompt (used when LLM prune is on)
You are the routing planner for a personal-finance copilot. Given the user
prompt and the candidate skills (each with a summary and applies_when),
return the minimal set of skills whose purpose the prompt actually calls for.
Prefer recall over precision; never invent a skill not in candidates; never
select the reviewer or execution — those are added automatically.
```

### 4.3 Combine algorithm

```python
def plan(prompt, context, candidates, policy):
    inferred = retrieve_or_llm(prompt, candidates)          # recall
    includes = {r.targets for r in policy.rules if r.when(context) and r.include}
    excludes = {r.targets for r in policy.rules if r.when(context) and r.exclude}
    leaves = (set(inferred) | includes | {policy.default_floor}) - excludes
    return leaves
```

### 4.4 Execution — in-process, not via the worker MA

The planner skill is fetched from the Registry like any skill (so its policy
is versioned) but executed by the orchestrator itself. It is **not** dispatched
through `build_worker_managed_agent` / `dispatch_managed_skill`. It is
privileged: always run, on the hot path, and trusted. v1 needs no LLM call at
all — retrieval + structured rules.

## 5. Deterministic resolver + scheduler

```python
def resolve_and_schedule(leaves, manifests, available_artifacts):
    selected = set(leaves)
    # 1. transitive prerequisite expansion
    frontier = list(leaves)
    while frontier:
        skill = frontier.pop()
        for artifact in manifests[skill].requires:
            if artifact in available_artifacts:
                continue                       # already satisfied — skip
            producer = producer_of(artifact, manifests)
            if producer and producer not in selected:
                selected.add(producer); frontier.append(producer)
    # 2. artifact-triggered mandatory skills/gates
    for skill, m in manifests.items():
        if m.mandatory_if and m.mandatory_if.satisfied(selected, manifests):
            selected.add(skill)
    # 3. topological layers; parallelize within a layer
    return topo_layers(selected, manifests)
```

- **Prerequisite skip** is the reuse win: "just draft this trade" pulls in
  `portfolio-analysis` only when there is no fresh `drift_report`.
- **`mandatory_if`** is how the reviewer re-enters whenever a
  `proposed_action` is in the selected set, regardless of intent.
- **Gates** (HITL, execution) stay as the existing `ctx.run_node` steps,
  fired by their trigger artifacts after the skill layers run.

## 6. Observability & evaluation

- Emit a `PLAN_CONSTRUCTED` audit event: `{prompt_hash, candidates, leaves,
  resolved, layers, policy_applied}` — reuse the existing audit infra
  (`emit_skill_invoked_audit` neighbours).
- Add eval fixtures under `evals/` asserting `prompt → selected skills` for
  representative intents (spending-only, onboarding, trade, research, mixed).
- Fallback: if retrieval/planner errors or returns empty, fall back to the
  default floor + any `mandatory_if` skills so the request never dead-ends.

## 7. Phase plan & task breakdown

### Phase 1 — Manifests (no behaviour change)
- [ ] Finalize manifest schema and artifact vocabulary (§2).
- [ ] Author manifests for the six skills (§3); decide front-matter vs
      `manifest.json`.
- [ ] Manifest loader + Pydantic validation in the orchestrator.
- [ ] Unit tests: every manifest parses; `produces`/`requires` reference known
      artifacts; the six reproduce the documented DAG.

### Phase 2 — Deterministic resolver + scheduler (behaviour-preserving)
- [ ] Build the `requires`/`produces` graph from manifests.
- [ ] Implement prerequisite expansion with already-satisfied skip.
- [ ] Implement `mandatory_if` and artifact-triggered gate injection.
- [ ] Topological layering; parallelize within a layer.
- [ ] Replace the hardcoded three-phase block in `root_planner` with the
      computed schedule; **input is still "all authorized."**
- [ ] Golden test: for the full set, the computed schedule == today's phases.

### Phase 3 — Planner + retrieval (the intelligence)
- [ ] Retrieval interface with a `list-all` implementation (default).
- [ ] In-process planner skill: structured policy block + combine algorithm.
- [ ] Default-floor skill + cold-start fallback.
- [ ] `PLAN_CONSTRUCTED` audit event + eval fixtures.
- [ ] Semantic-search retrieval implementation behind the interface
      (enabled when catalog size warrants).
- [ ] Optional LLM prune, added once over-selection is observed.

## 8. Open questions

1. **Manifest home** — SKILL.md front-matter (one file, travels with docs)
   vs sibling `manifest.json` (clean parse, no markdown stripping). Leaning
   front-matter to keep one source of truth per skill.
2. **Semantic query** — embed the raw prompt vs a cheap extracted-intent
   step first (strips pleasantries, improves recall). Decide when semantic
   retrieval is actually switched on.
3. **Planner policy schema** — precedence when a rule includes and another
   excludes the same skill (proposal: explicit `exclude` wins), and how the
   NL prompt and structured rules compose under the LLM prune.
4. **Default-floor identity** — reuse `spending-analysis`, or add a
   purpose-built lightweight "overview" skill as the baseline.
