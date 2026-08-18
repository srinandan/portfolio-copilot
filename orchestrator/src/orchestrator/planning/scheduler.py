"""Deterministic resolver + scheduler (ADR-0022, Phase 2).

Turns a set of intent-selected *leaf* skills into an ordered, layered execution
plan using only the skills' manifests — no hardcoded phase structure. Three
deterministic steps (design §5):

1. **Prerequisite expansion** — pull in each leaf's transitive ``requires``
   producers, *skipping* any artifact already available from session state.
2. **Mandatory injection** — add any skill whose ``mandatory_if`` trigger is
   satisfied by the selected set (this is how the reviewer re-enters whenever a
   ``proposed_action`` will be produced — structural compliance, not planner
   discretion).
3. **Topological layering** — order the selected skills so every skill runs
   after the producers of the artifacts it consumes (``requires`` *and*
   ``optional``); skills in the same layer are independent and may run
   concurrently.

The current hand-written three-phase order (independent → parallel → dependent)
becomes an *emergent property* of the dependency graph. See
``docs/design/intent-driven-skill-planning.md`` §5/§7.

This module is pure: it takes manifests + selected leaves and returns a plan.
It performs no I/O and knows nothing about how skills are dispatched.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Sequence

from ..skills.manifest import Artifact, SkillManifest, producer_of


class SchedulerError(RuntimeError):
    """Raised when a plan cannot be scheduled (e.g. a dependency cycle)."""


@dataclass(frozen=True)
class ScheduledPlan:
    """The computed execution plan.

    ``layers`` is ordered outer-to-inner: layer *i* runs only after every
    earlier layer completes, and skills within a layer are mutually independent.
    Names are clean skill ids (no ``private-`` prefix).
    """

    layers: tuple[tuple[str, ...], ...]
    selected: frozenset[str]

    def flat(self) -> tuple[str, ...]:
        """All selected skills in scheduled order (layers flattened)."""
        return tuple(name for layer in self.layers for name in layer)


def _consumed_artifacts(manifest: SkillManifest) -> tuple[Artifact, ...]:
    """Artifacts a skill reads — required *and* optional.

    Both create *ordering* edges (a consumer runs after a selected producer),
    but only ``requires`` drives prerequisite *expansion* (adding a producer
    that wasn't selected). Optional inputs are used-if-present, never pulled in.
    """
    return (*manifest.requires, *manifest.optional)


def _canonical_key(canonical_order: Optional[Sequence[str]]):
    order = list(canonical_order or [])
    index = {name: i for i, name in enumerate(order)}

    def key(name: str) -> tuple[int, str]:
        # Known skills sort by canonical position; unknown ones sort after, by name.
        return (index.get(name, len(order)), name)

    return key


def resolve_and_schedule(
    leaves: Iterable[str],
    manifests: Mapping[str, SkillManifest],
    available_artifacts: Iterable[str] = (),
    canonical_order: Optional[Sequence[str]] = None,
) -> ScheduledPlan:
    """Resolve prerequisites and topologically schedule the selected skills.

    Args:
        leaves: intent-selected skill ids (clean names). In Phase 2 this is the
            full set of authorized skills; in Phase 3 it is the planner's
            intent leaves.
        manifests: the schedulable universe, keyed by clean skill id. Only
            skills present here can be selected, expanded, or injected — this is
            what bounds prerequisite expansion to *authorized* skills.
        available_artifacts: artifacts already satisfied from session state
            (e.g. a fresh drift report, an existing active IPS). A required
            artifact that is already available is not expanded into its producer.
        canonical_order: tie-break order for skills within a layer, so the plan
            is deterministic and matches the historical pipeline order. Skills
            not listed sort last, by name.

    Returns:
        A :class:`ScheduledPlan` whose layers respect every dependency.

    Raises:
        SchedulerError: if the selected skills contain a dependency cycle.
    """
    pool = dict(manifests)
    available = {str(a) for a in available_artifacts}
    selected: set[str] = {name for name in leaves if name in pool}

    # --- 1. transitive prerequisite expansion (requires only) ----------------
    frontier = list(selected)
    while frontier:
        skill = frontier.pop()
        for artifact in pool[skill].requires:
            if artifact.value in available:
                continue  # already satisfied from session state — no producer needed
            producer = producer_of(artifact, pool)
            if producer is not None and producer not in selected:
                selected.add(producer)
                frontier.append(producer)
            # No producer in the authorized pool → treated as an external/preloaded
            # input (holdings, research_question, or a session-provided IPS).

    # --- 2. artifact-triggered mandatory injection ---------------------------
    # Iterate to a fixpoint: injecting a skill can produce new artifacts that
    # trigger further mandatory skills, and can itself require expansion.
    changed = True
    while changed:
        changed = False
        produced = {a.value for name in selected for a in pool[name].produces} | available
        for name, manifest in pool.items():
            if name in selected or manifest.mandatory_if is None:
                continue
            if manifest.mandatory_if.satisfied(produced):
                selected.add(name)
                changed = True
                # Expand the newly injected skill's prerequisites too.
                frontier = [name]
                while frontier:
                    skill = frontier.pop()
                    for artifact in pool[skill].requires:
                        if artifact.value in available:
                            continue
                        producer = producer_of(artifact, pool)
                        if producer is not None and producer not in selected:
                            selected.add(producer)
                            frontier.append(producer)

    # --- 3. topological layering --------------------------------------------
    # Edge: consumer depends on any *selected* producer of an artifact it reads.
    deps: dict[str, set[str]] = {name: set() for name in selected}
    for consumer in selected:
        for artifact in _consumed_artifacts(pool[consumer]):
            producer = producer_of(artifact, {n: pool[n] for n in selected})
            if producer is not None and producer != consumer:
                deps[consumer].add(producer)

    key = _canonical_key(canonical_order)
    layers: list[tuple[str, ...]] = []
    done: set[str] = set()
    remaining = set(selected)
    while remaining:
        ready = [name for name in remaining if deps[name] <= done]
        if not ready:
            raise SchedulerError(
                f"dependency cycle among skills: {sorted(remaining)}"
            )
        ready.sort(key=key)
        layers.append(tuple(ready))
        done.update(ready)
        remaining.difference_update(ready)

    return ScheduledPlan(layers=tuple(layers), selected=frozenset(selected))
