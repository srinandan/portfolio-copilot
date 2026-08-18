"""Deterministic plan construction (ADR-0022).

The back half of the Retrieve → Plan → Resolve → Schedule pipeline: given a set
of selected skills and their manifests, expand prerequisites, inject
artifact-triggered mandatory skills, and topologically layer the result for
execution. See ``docs/adr/0022-intent-driven-skill-planning.md``.

Phase 2 wires :func:`resolve_and_schedule` into the planner in place of the
hardcoded three-phase block; the front half (retrieval + intent policy) lands
in Phase 3.
"""

from .intent import IntentSignals, classify_intent
from .policy import (
    DEFAULT_POLICY,
    Op,
    PlannerPolicy,
    PolicyRule,
    Predicate,
    applied_rules,
    select_leaves,
)
from .scheduler import ScheduledPlan, SchedulerError, resolve_and_schedule

__all__ = [
    "ScheduledPlan",
    "SchedulerError",
    "resolve_and_schedule",
    "Op",
    "Predicate",
    "PolicyRule",
    "PlannerPolicy",
    "select_leaves",
    "applied_rules",
    "DEFAULT_POLICY",
    "IntentSignals",
    "classify_intent",
]
