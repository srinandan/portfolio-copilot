"""Eval fixtures: prompt → selected skills (ADR-0022 §6, Phase 3b).

Exercises the front half of the pipeline end to end — list-all retrieval →
keyword intent → structured policy — asserting which leaves get selected for
representative intents. This is the `prompt → selected skills` contract the ADR
calls for; the deterministic resolver/scheduler is covered by test_scheduler.
"""

import pytest

from orchestrator.planning import DEFAULT_POLICY, DEFAULT_RETRIEVER, classify_intent, select_leaves
from orchestrator.skills.manifest import load_all_manifests

MANIFESTS = load_all_manifests()


def _leaves(prompt: str, has_active_ips: bool) -> set[str]:
    candidates = [c.id for c in DEFAULT_RETRIEVER.retrieve(prompt, MANIFESTS)]
    context = dict(classify_intent(prompt).as_context())
    context["has_active_ips"] = has_active_ips
    return select_leaves(candidates, context, DEFAULT_POLICY)


# (prompt, has_active_ips, must_include, must_exclude)
CASES = [
    ("what did I spend on dining last month?", True, {"spending-analysis"}, {"goals-onboarding"}),
    ("how is my portfolio doing?", True, {"portfolio-analysis", "spending-analysis"}, {"goals-onboarding"}),
    ("should I trim my tech exposure?", True, {"action-drafting", "portfolio-analysis"}, {"goals-onboarding"}),
    ("sell 20 shares of NVDA", True, {"action-drafting"}, {"goals-onboarding"}),
    ("help me set up my financial goals", False, {"goals-onboarding", "spending-analysis"}, set()),
]


@pytest.mark.parametrize("prompt,has_ips,must_include,must_exclude", CASES)
def test_prompt_selects_expected_skills(prompt, has_ips, must_include, must_exclude):
    leaves = _leaves(prompt, has_ips)
    assert must_include <= leaves, f"{prompt!r} → {sorted(leaves)}"
    assert must_exclude.isdisjoint(leaves), f"{prompt!r} → {sorted(leaves)}"


def test_floor_always_present():
    # The default floor (spending-analysis) is selected for every prompt/state.
    for prompt, has_ips, _, _ in CASES:
        assert "spending-analysis" in _leaves(prompt, has_ips)


def test_trade_prompt_adds_action_even_when_not_a_candidate():
    # If retrieval somehow omitted action-drafting, the trade-intent include still
    # pulls it in (policy augments retrieval).
    context = dict(classify_intent("rebalance my portfolio").as_context())
    context["has_active_ips"] = True
    leaves = select_leaves(["portfolio-analysis"], context, DEFAULT_POLICY)
    assert "action-drafting" in leaves
