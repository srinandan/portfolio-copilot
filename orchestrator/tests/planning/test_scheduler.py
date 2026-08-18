"""Tests for the deterministic resolver + scheduler (ADR-0022, Phase 2).

The golden test asserts that scheduling the full six-skill set from their
manifests reproduces today's dependency structure (independent → portfolio →
action → reviewer), so the Phase 2 change is behaviour-preserving.
"""

import pytest

from orchestrator.planning import ScheduledPlan, SchedulerError, resolve_and_schedule
from orchestrator.skills.manifest import SkillManifest, load_all_manifests, producer_of

# Clean-name canonical order, mirroring the planner's PIPELINE_SKILL_ORDER.
CANONICAL = [
    "spending-analysis",
    "goals-onboarding",
    "portfolio-analysis",
    "research",
    "action-drafting",
    "reviewer",
]


@pytest.fixture
def manifests():
    return load_all_manifests()


def _schedule(leaves, manifests, available=()):
    return resolve_and_schedule(leaves, manifests, available_artifacts=available, canonical_order=CANONICAL)


def _assert_dependency_order(plan: ScheduledPlan, manifests) -> None:
    """Every skill must appear after the producers of the artifacts it reads."""
    position = {name: i for i, layer in enumerate(plan.layers) for name in layer}
    for name in plan.selected:
        m = manifests[name]
        for artifact in (*m.requires, *m.optional):
            producer = producer_of(artifact, {n: manifests[n] for n in plan.selected})
            if producer and producer != name:
                assert position[producer] < position[name], (
                    f"{name} scheduled before its producer {producer} for {artifact.value}"
                )


# --------------------------------------------------------------------------- #
# Golden: full set reproduces today's dependency schedule                      #
# --------------------------------------------------------------------------- #


def test_full_set_reproduces_documented_schedule(manifests):
    plan = _schedule(CANONICAL, manifests)
    assert plan.layers == (
        ("spending-analysis", "goals-onboarding", "research"),
        ("portfolio-analysis",),
        ("action-drafting",),
        ("reviewer",),
    )


def test_full_set_dependency_order_holds(manifests):
    plan = _schedule(CANONICAL, manifests)
    _assert_dependency_order(plan, manifests)
    # The historical dependency spine: goals → portfolio → action → reviewer.
    flat = plan.flat()
    assert flat.index("goals-onboarding") < flat.index("portfolio-analysis")
    assert flat.index("portfolio-analysis") < flat.index("action-drafting")
    assert flat.index("action-drafting") < flat.index("reviewer")
    # research must precede action-drafting (its optional research_briefs input).
    assert flat.index("research") < flat.index("action-drafting")


def test_within_layer_canonical_order(manifests):
    plan = _schedule(CANONICAL, manifests)
    # Layer 0 holds the three independents in canonical order.
    assert plan.layers[0] == ("spending-analysis", "goals-onboarding", "research")


# --------------------------------------------------------------------------- #
# Prerequisite expansion & already-satisfied skip                              #
# --------------------------------------------------------------------------- #


def test_expansion_pulls_in_required_producers(manifests):
    # Just "draft a trade" — no available artifacts. Expansion must pull in
    # portfolio-analysis (drift_report) and goals-onboarding (active_ips);
    # research is only optional, so it is NOT pulled in.
    plan = _schedule(["action-drafting"], manifests)
    assert "portfolio-analysis" in plan.selected
    assert "goals-onboarding" in plan.selected
    assert "research" not in plan.selected
    _assert_dependency_order(plan, manifests)


def test_already_satisfied_artifacts_are_not_expanded(manifests):
    # A fresh drift_report + existing IPS/holdings in session state: drafting
    # should NOT re-run portfolio-analysis or goals-onboarding.
    plan = _schedule(
        ["action-drafting"],
        manifests,
        available=["drift_report", "active_ips", "holdings"],
    )
    assert "portfolio-analysis" not in plan.selected
    assert "goals-onboarding" not in plan.selected


def test_partial_expansion_pulls_only_missing_producer(manifests):
    # drift_report missing but IPS/holdings available: pull in portfolio-analysis
    # (produces drift_report) but not goals-onboarding (active_ips is available).
    plan = _schedule(
        ["action-drafting"],
        manifests,
        available=["active_ips", "holdings"],
    )
    assert "portfolio-analysis" in plan.selected
    assert "goals-onboarding" not in plan.selected


def test_authorized_subset_treats_missing_producers_as_preloaded():
    # Only PA + AD authorized (the end-to-end test's scenario). active_ips has no
    # producer in this pool, so it is assumed preloaded — goals is NOT invented.
    pool = {n: m for n, m in load_all_manifests().items() if n in ("portfolio-analysis", "action-drafting")}
    plan = _schedule(["portfolio-analysis", "action-drafting"], pool)
    assert plan.selected == {"portfolio-analysis", "action-drafting"}
    assert plan.layers == (("portfolio-analysis",), ("action-drafting",))


# --------------------------------------------------------------------------- #
# Mandatory injection (structural compliance)                                  #
# --------------------------------------------------------------------------- #


def test_reviewer_injected_when_proposed_action_produced(manifests):
    # Reviewer is not a leaf, but action-drafting produces proposed_action, so
    # the reviewer's mandatory_if fires and it is injected — never optional.
    plan = _schedule(["action-drafting"], manifests, available=["drift_report", "active_ips", "holdings"])
    assert "reviewer" in plan.selected
    flat = plan.flat()
    assert flat.index("action-drafting") < flat.index("reviewer")


def test_reviewer_not_injected_without_proposed_action(manifests):
    # No proposed_action anywhere → reviewer stays out.
    plan = _schedule(["spending-analysis"], manifests)
    assert "reviewer" not in plan.selected
    assert plan.layers == (("spending-analysis",),)


# --------------------------------------------------------------------------- #
# Cycles & edge cases                                                          #
# --------------------------------------------------------------------------- #


def _manifest(**kw) -> SkillManifest:
    base = dict(id="x", summary="s", applies_when="w", parallelizable=True)
    base.update(kw)
    return SkillManifest.model_validate(base)


def test_cycle_raises():
    # a needs drift_report (from b); b needs proposed_action (from a) → cycle.
    pool = {
        "a": _manifest(id="a", requires=["drift_report"], produces=["proposed_action"]),
        "b": _manifest(id="b", requires=["proposed_action"], produces=["drift_report"]),
    }
    with pytest.raises(SchedulerError, match="cycle"):
        resolve_and_schedule(["a", "b"], pool, canonical_order=["a", "b"])


def test_empty_leaves_yield_empty_plan(manifests):
    plan = _schedule([], manifests)
    assert plan.layers == ()
    assert plan.selected == frozenset()


def test_leaves_outside_pool_are_ignored(manifests):
    plan = _schedule(["spending-analysis", "not-a-skill"], manifests)
    assert plan.selected == {"spending-analysis"}
