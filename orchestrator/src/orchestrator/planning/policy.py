"""Planner routing policy (ADR-0022, Phase 3b).

The **Plan** stage of the Retrieve → Plan → Resolve → Schedule pipeline. Given
the retrieval *candidates*, a decision *context*, and a *policy*, it computes the
intent **leaves** — the user-facing goals the prompt actually calls for. The
deterministic resolver/scheduler (:mod:`.scheduler`) then adds prerequisites and
gates and orders everything.

Policy is expressed as a natural-language prompt **and** a structured rules block
(design §4.2, decision "both"). This module implements the *structured* block —
what v1 evaluates; the NL prompt feeds the optional LLM prune added later. Rule
conditions are **structured predicates** (field / op / value over the context
dict), never free-form expressions, so nothing here evaluates arbitrary strings.

Selection is recall-biased (design §3): over-selecting only costs latency, while
under-selecting silently returns incomplete financial advice. So the default
floor is exclude-proof — it always survives, guaranteeing a non-empty plan.

This module is pure: no I/O. The context is assembled by the caller (state facts
from Firestore/session + prompt intent from :mod:`.intent`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Optional


class Op(str, Enum):
    """The predicate operators the policy schema supports."""

    EQ = "eq"          # context[field] == value
    NE = "ne"          # context[field] != value
    TRUTHY = "truthy"  # bool(context[field]) is True   (value ignored)
    FALSY = "falsy"    # bool(context[field]) is False  (value ignored; missing counts)
    IN = "in"          # context[field] in value        (value is a collection)
    CONTAINS = "contains"  # value in context[field]     (field holds a collection)


def _lookup(context: Mapping[str, Any], field_path: str) -> Any:
    """Reads a (optionally dotted) key from the context, or None if absent."""
    current: Any = context
    for part in field_path.split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        else:
            return None
    return current


@dataclass(frozen=True)
class Predicate:
    """A structured condition over the decision context: ``field <op> value``."""

    field: str
    op: Op
    value: Any = None

    def evaluate(self, context: Mapping[str, Any]) -> bool:
        actual = _lookup(context, self.field)
        if self.op is Op.EQ:
            return actual == self.value
        if self.op is Op.NE:
            return actual != self.value
        if self.op is Op.TRUTHY:
            return bool(actual)
        if self.op is Op.FALSY:
            return not bool(actual)
        if self.op is Op.IN:
            try:
                return actual in (self.value or ())
            except TypeError:
                return False
        if self.op is Op.CONTAINS:
            try:
                return self.value in (actual or ())
            except TypeError:
                return False
        raise ValueError(f"unsupported predicate op: {self.op!r}")  # pragma: no cover


@dataclass(frozen=True)
class PolicyRule:
    """A routing rule: when ``when`` holds, contribute ``include`` / ``exclude``.

    ``when=None`` means the rule always applies. Skill ids are clean names.
    """

    name: str
    when: Optional[Predicate] = None
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()

    def applies(self, context: Mapping[str, Any]) -> bool:
        return self.when is None or self.when.evaluate(context)


@dataclass(frozen=True)
class PlannerPolicy:
    """The structured routing policy: a cold-start floor plus include/exclude rules."""

    default_floor: Optional[str] = None
    rules: tuple[PolicyRule, ...] = field(default_factory=tuple)


def select_leaves(
    candidates: Iterable[str],
    context: Mapping[str, Any],
    policy: PlannerPolicy,
) -> set[str]:
    """Computes the intent leaves from candidates + context + policy.

    ``leaves = ((candidates ∪ includes) − excludes) ∪ {default_floor}``

    Explicit excludes win over includes and over the candidate set, but **not**
    over the default floor: the floor is always contributed as the baseline, so
    the plan is never empty (design §4.2, §5). Authorization is enforced
    downstream — the scheduler only runs leaves it has a manifest for — so this
    may name a skill that later turns out unauthorized; that skill is simply
    dropped there.
    """
    inferred = set(candidates)
    includes: set[str] = set()
    excludes: set[str] = set()
    applied: list[str] = []
    for rule in policy.rules:
        if rule.applies(context):
            applied.append(rule.name)
            includes.update(rule.include)
            excludes.update(rule.exclude)

    leaves = (inferred | includes) - excludes
    if policy.default_floor:
        leaves.add(policy.default_floor)
    return leaves


def applied_rules(context: Mapping[str, Any], policy: PlannerPolicy) -> list[str]:
    """Names of the rules whose condition holds — for the PLAN_CONSTRUCTED audit."""
    return [rule.name for rule in policy.rules if rule.applies(context)]


# --------------------------------------------------------------------------- #
# The default policy (design §4.2). v1 rule set, agreed for Phase 3b:          #
#   - the cold-start floor is `spending-analysis`;                            #
#   - an explicit trade intent pulls in the trade path (include-only, so a    #
#     false positive is harmless — action-drafting self-skips with no drift); #
#   - onboarding is skipped once the user already has an active IPS.          #
# Intent-driven *excludes* are deliberately deferred until the LLM/semantic   #
# pass can classify intent reliably (recall-bias).                            #
# --------------------------------------------------------------------------- #
DEFAULT_POLICY = PlannerPolicy(
    default_floor="spending-analysis",
    rules=(
        PolicyRule(
            name="trade-intent-include",
            when=Predicate("requested_trade", Op.TRUTHY),
            include=("action-drafting",),
        ),
        PolicyRule(
            name="onboarding-once",
            when=Predicate("has_active_ips", Op.TRUTHY),
            exclude=("goals-onboarding",),
        ),
    ),
)
