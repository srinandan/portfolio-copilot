"""Wiring tests for the equity-research advisory path (issue #344).

Proves that with the two new skills added to the schedulable set, the manifest
dependency graph is consistent and the scheduler orders equity-research before
suitability (suitability requires the equity_assessment that equity-research
produces). The two skills are NOT in DEFAULT_MANIFEST_SKILLS yet (activation is a
separate, reviewed step), so the live planner is unaffected — this validates the
graph for that future activation.
"""

from orchestrator.planning.scheduler import resolve_and_schedule
from orchestrator.skills.manifest import (
    DEFAULT_MANIFEST_SKILLS,
    Artifact,
    load_all_manifests,
    validate_manifest_graph,
)

EIGHT_SKILLS = list(DEFAULT_MANIFEST_SKILLS) + ["equity-research", "suitability"]


def test_new_artifacts_exist():
    assert Artifact.EQUITY_QUERY.value == "equity_query"
    assert Artifact.EQUITY_ASSESSMENT.value == "equity_assessment"
    assert Artifact.EQUITY_RECOMMENDATION.value == "equity_recommendation"


def test_equity_manifests_load_and_validate():
    manifests = load_all_manifests(EIGHT_SKILLS)
    # No exception => the requires/produces graph across all eight is consistent.
    validate_manifest_graph(manifests)

    assert Artifact.EQUITY_ASSESSMENT in manifests["equity-research"].produces
    assert Artifact.EQUITY_ASSESSMENT in manifests["suitability"].requires
    assert Artifact.EQUITY_RECOMMENDATION in manifests["suitability"].produces


def test_scheduler_orders_research_before_suitability():
    manifests = load_all_manifests(EIGHT_SKILLS)
    # active_ips + holdings satisfied from session state so we isolate the
    # equity_assessment dependency; equity-research is pulled in as its producer.
    plan = resolve_and_schedule(
        ["suitability"],
        manifests,
        available_artifacts=("active_ips", "holdings"),
    )
    flat = plan.flat()
    assert "equity-research" in flat
    assert "suitability" in flat
    assert flat.index("equity-research") < flat.index("suitability")


def test_unknown_equity_leaves_dropped_by_six_skill_pool():
    # With only the default six in the pool, an equity leaf is silently dropped
    # (the mechanism that makes the policy rule inert until activation).
    manifests = load_all_manifests()  # the six
    plan = resolve_and_schedule(["equity-research", "suitability", "spending-analysis"], manifests)
    assert "equity-research" not in plan.flat()
    assert "suitability" not in plan.flat()
    assert "spending-analysis" in plan.flat()
