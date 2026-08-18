# ADR-0022: Intent-driven skill planning — semantic search, an in-process planner skill, and self-describing manifests

## Status
**Accepted — implemented.** The core pipeline (Retrieve → Plan → Resolve →
Schedule) ships: self-describing manifests, the deterministic resolver +
scheduler, registry-sourced manifest retrieval, the in-process policy (structured
predicates + keyword intent), and the `PLAN_CONSTRUCTED` audit + UI plan
pre-render. Semantic-search retrieval and the optional LLM prune are deferred
behind the retrieval/policy interfaces, to enable when catalog size or observed
over-selection warrant. See the companion design doc §7 for the phase-to-PR map.

Refines [ADR-0004](0004-dynamic-planning-over-fixed-pipeline.md): it makes
0004's "the planner composes its own plan from what it finds" concrete, and
— for the Reviewer and human-approval gates — supersedes 0004's "the planner
itself decides when an action is high-stakes" in favour of deterministic,
artifact-triggered gating (see *Compliance gates are structural* below).

Consistent with [ADR-0016](0016-deterministic-primitives-in-orchestrator.md):
structure and safety stay deterministic in the orchestrator; the LLM is used
only where genuine judgement is required (reading intent).

## Context

ADR-0004 committed the project to registry-driven dynamic planning rather
than a fixed multi-agent pipeline. The shipped orchestrator
(`orchestrator/src/orchestrator/planner.py`) realizes only the *discovery*
half of that vision:

1. `root_planner` calls `AgentRegistryClient.list_authorized_skills()`
   (`registry_client.py:177`), which returns **every** skill and drops those
   in `TARGET_STATE_DISABLED`.
2. It intersects that list against a hardcoded whitelist of six
   `SKILL_PLANS` (`planner.py:409`, `:604`).
3. It runs **all** of the surviving skills, every cycle, in a fixed
   three-phase order (`planner.py:654`: independent → parallel → dependent),
   then always evaluates the HITL approval and Alpaca execution gates.

There is no reading of the user's intent. "The plan" is "run everything
authorized." The only per-skill selection is the implicit self-skips buried
in each `build_input` (research skips with no question, reviewer skips with
no drafted action, etc.).

Two forces break this as the skill catalog grows:

- **Not every prompt needs every skill.** Running portfolio analysis,
  research, drafting and review for *"what did I spend on dining last
  month?"* wastes latency and tokens and clutters the planning trace.
- **Adding a skill is not free.** A new skill must be added to the hardcoded
  whitelist, slotted into the phase groups, and given bespoke
  `build_input`/`postprocess`. The registry can only *subtract* skills from
  the pipeline, never *add* one the code doesn't already know.

A further constraint shapes the solution: **`list` is coarse.**
Authorization is all-or-nothing at the principal level, so
`list_authorized_skills()` is not a selection signal. Real selection has to
come from **intent**, with per-skill authorization enforced at *fetch* time.

## Decision

Construct the plan in four stages — **Retrieve → Plan → Resolve →
Schedule** — and make skills self-describing so both routing and dependency
resolution become data-driven.

```
prompt ─▶ RETRIEVE ──▶ PLAN ──▶ RESOLVE ──▶ SCHEDULE
          semantic     planner   requires/    topo-sort
          search       skill      produces     + gates
          (recall)     (policy)   (structure)  (order)
          └── candidate generation ──┘ └── deterministic back half ──┘
```

### 1. Self-describing skill manifests

Every skill ships a machine-readable manifest (SKILL.md front-matter, or a
sibling `manifest.json` in the registry revision zip) declaring: `summary`,
`applies_when`, `requires`, `produces`, `parallelizable`, and `mandatory_if`.

**Policy and structure are deliberately separated.** *Structure*
(dependencies — "action-drafting needs a drift report") lives in the
manifest, with the skill. *Policy* (intent — "for a trade prompt, include the
trade path") lives in the planner. If the planner owned dependencies it would
have to know every skill's wiring, and adding a skill would mean editing the
planner again — the exact centralization we are removing. Keeping
dependencies with the skill is what makes the system scale.

### 2. Retrieve via semantic search

Replace "list everything" with a semantic query derived from the prompt,
run against the Agent Registry, yielding intent-relevant *candidates*.
Per-skill authorization and `TARGET_STATE_DISABLED` are enforced at **fetch**
(`get_skill_content`, `registry_client.py:221`); any candidate that cannot be
fetched is silently dropped. This preserves the "registry can only subtract"
safety property (and live revocation), now enforced at fetch rather than at
the list-filter.

Retrieval sits behind a **pluggable interface**. `list-all` remains the
implementation until the catalog outgrows a single planner context; semantic
search then slots in with no change to callers.

### 3. Plan via an in-process planner skill

A privileged, always-run **planner skill** captures routing *policy*. Its
policy is versioned in the Registry like any skill, but the orchestrator
executes it **directly, in-process — not through the worker Managed Agent**
— because it is on the hot path of every request and must be trusted. This
removes both the bootstrapping problem (the planner cannot itself be
intent-selected) and the extra remote round-trip.

The planner skill is expressed as **both**:

- a natural-language **prompt** (for LLM intent reasoning), and
- a structured **policy block** (deterministic mandatory-include /
  intent-exclude rules, and the default floor).

The executed leaf set is:

```
leaves = ( semantic_candidates ∪ policy_includes ) − policy_excludes
```

Union is **recall-biased**: over-selection only costs latency, whereas
under-selection silently returns incomplete financial advice. **v1 runs
retrieval + rules only** (no LLM prune); the LLM precision pass is added once
over-selection is observed in practice.

### 4. Resolve and schedule, deterministically

From the manifests' `requires`/`produces`, the orchestrator:

1. expands each selected leaf with its transitive prerequisites, **skipping
   any artifact already satisfied** from session state (a fresh drift report,
   an existing active IPS);
2. injects artifact-triggered gates (below);
3. topologically sorts into layers and dispatches, running independent
   layers in parallel.

The current hand-written three-phase order becomes an **emergent property**
of the dependency graph rather than a hardcoded structure.

### Compliance gates are structural, not discretionary

This is the deliberate refinement of ADR-0004. Rather than the planner
judging when an action is "high-stakes" enough to warrant review, the
**Reviewer, HITL approval, and execution gates are triggered by the presence
of a drafted `ProposedAction`** (`requires: [proposed_action]`,
`mandatory_if`). The reviewer already behaves this way in code
(`_build_reviewer_input` returns `None` with no drafted action,
`planner.py:299`); this ADR makes it a declared, enforced property. A user
never has to ask for a review, and the planner can never elect to skip one.
Compliance is a property of the artifact graph, not the model's judgement.

### Cold-start floor: a default-set skill

To guarantee the pipeline never dead-ends when retrieval returns nothing and
no policy rule fires, one skill is designated the **default floor** (a
manifest flag / policy entry), always contributed by the planner as a
baseline. Because it is itself a registry skill, the floor is configurable
without code — the same mechanism as any policy rule, and it doubles as the
"always run these" hook.

## Why this keeps ADR-0004's story — and scales

- **The governance narrative survives and gets more legible:** a planning
  trace now reads *"prompt → retrieved N candidates → selected M by intent →
  resolved K prerequisites → 3 parallel layers,"* instead of "ran all 6."
- **Live revocation still works,** enforced at fetch-time authorization.
- **It finally scales:** adding a skill is *ship the skill + its manifest*.
  Routing picks it up with no planner or orchestrator edits, because
  structure travels with the skill and only genuinely new *policy* ever
  touches the planner.

## Consequences

- **A new nondeterministic component** (intent selection) enters the hot
  path. Mitigated by: recall-biased union, deterministic dependency
  resolution and mandatory gates *around* it, the default floor, a
  `PLAN_CONSTRUCTED` audit event, and eval fixtures asserting
  `prompt → selected skills`.
- **Manifests must be authored and kept truthful.** A stale
  `requires`/`produces` silently mis-schedules. Owned with the skill and
  covered by tests.
- **Not yet fully "drop a skill and go."** `build_input`/`postprocess` remain
  bespoke per skill (the ADR-0016 pre-computation boundary). The manifest
  makes *routing* free; a generic manifest-driven preloader (resolve
  `requires` by name from a shared artifact store) would make the *data
  plane* declarative too — a follow-on, out of scope here.
- **Semantic-search quality depends on manifest text.** Retrieval and
  embeddings need their own eval as the catalog grows.
- **One extra planner step per request,** kept cheap by running in-process
  and, in v1, without an LLM.

## Rollout

- **Phase 1 — Manifests.** Define the schema; backfill the six existing
  skills; add a loader + validation. No behaviour change (the planner still
  runs all authorized skills).
- **Phase 2 — Deterministic resolver + scheduler.** Build the
  `requires`/`produces` graph, dependency expansion, artifact-triggered
  gates, and topological scheduling. Replace the hardcoded three-phase
  structure with the computed schedule, still selecting "all authorized" as
  input. Behaviour-preserving and fully testable.
- **Phase 3 — Planner + retrieval.** Add the in-process planner skill
  (retrieval + rules), the default-floor skill, the `PLAN_CONSTRUCTED` audit
  event, and eval fixtures. Start with `list-all` retrieval; introduce
  semantic search behind the retrieval interface when catalog size warrants.
  Add the optional LLM prune last.

Concrete schemas, example manifests for the six skills, the planner contract,
and the phase task breakdown live in the companion design doc:
[`docs/design/intent-driven-skill-planning.md`](../design/intent-driven-skill-planning.md).

## Open questions

- **Manifest home:** SKILL.md front-matter vs a sibling `manifest.json` in
  the revision zip.
- **Semantic query construction:** embed the raw prompt vs an extracted
  intent.
- **Planner policy schema:** how the natural-language prompt and the
  structured rules block interact and compose.
- **Default-floor identity:** which skill (or a purpose-built one) is the
  baseline.
