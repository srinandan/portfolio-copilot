"""Tests for self-describing skill manifests (ADR-0022, Phase 1).

Covers: every shipped manifest parses; requires/produces reference the known
artifact vocabulary; the six manifests reproduce the documented DAG (design
§3); mandatory_if grammar; and the loader/validation failure modes.
"""

import pytest

from orchestrator.skills.manifest import (
    DEFAULT_MANIFEST_SKILLS,
    Artifact,
    MandatoryIf,
    SkillManifest,
    SkillManifestError,
    load_all_manifests,
    load_manifest,
    producer_of,
    validate_manifest_graph,
    verify_all_manifests,
)

# The dependency graph the design (docs/design/intent-driven-skill-planning.md
# §3) says the six shipped skills must describe. This table is the golden
# reference: Phase 2's resolver must reproduce today's phase order from it.
EXPECTED = {
    "spending-analysis": {
        "requires": set(),
        "optional": set(),
        "produces": {Artifact.SPENDING_REPORT},
        "parallelizable": True,
        "mandatory_if": None,
    },
    "goals-onboarding": {
        "requires": set(),
        "optional": set(),
        "produces": {Artifact.ACTIVE_IPS},
        "parallelizable": True,
        "mandatory_if": None,
    },
    "portfolio-analysis": {
        "requires": {Artifact.ACTIVE_IPS, Artifact.HOLDINGS},
        "optional": set(),
        "produces": {Artifact.DRIFT_REPORT},
        "parallelizable": True,
        "mandatory_if": None,
    },
    "research": {
        "requires": {Artifact.RESEARCH_QUESTION},
        "optional": set(),
        "produces": {Artifact.RESEARCH_BRIEFS},
        "parallelizable": True,
        "mandatory_if": None,
    },
    "action-drafting": {
        "requires": {Artifact.DRIFT_REPORT, Artifact.ACTIVE_IPS, Artifact.HOLDINGS},
        "optional": {Artifact.RESEARCH_BRIEFS},
        "produces": {Artifact.PROPOSED_ACTION},
        "parallelizable": False,
        "mandatory_if": None,
    },
    "reviewer": {
        "requires": {Artifact.PROPOSED_ACTION, Artifact.ACTIVE_IPS, Artifact.HOLDINGS},
        "optional": set(),
        "produces": {Artifact.REVIEWER_VERDICT},
        "parallelizable": False,
        "mandatory_if": Artifact.PROPOSED_ACTION,
    },
}


# --------------------------------------------------------------------------- #
# Loading & schema                                                            #
# --------------------------------------------------------------------------- #


def test_default_manifest_skills_matches_expected():
    assert set(DEFAULT_MANIFEST_SKILLS) == set(EXPECTED)


def test_all_manifests_load():
    manifests = load_all_manifests()
    assert set(manifests) == set(EXPECTED)
    for name, m in manifests.items():
        assert isinstance(m, SkillManifest)
        assert m.id == name
        assert m.summary.strip()
        assert m.applies_when.strip()


@pytest.mark.parametrize("skill", sorted(EXPECTED))
def test_manifest_matches_documented_dag(skill):
    m = load_manifest(skill)
    exp = EXPECTED[skill]
    assert set(m.requires) == exp["requires"]
    assert set(m.optional) == exp["optional"]
    assert set(m.produces) == exp["produces"]
    assert m.parallelizable is exp["parallelizable"]
    if exp["mandatory_if"] is None:
        assert m.mandatory_if is None
    else:
        assert m.mandatory_if is not None
        assert m.mandatory_if.artifact == exp["mandatory_if"]
    # Phase 1 designates no cold-start floor (open question #4).
    assert m.default is False


def test_load_manifest_accepts_private_prefixed_name():
    # Loader normalizes registry-style names.
    assert load_manifest("private-reviewer").id == "reviewer"


def test_requires_and_produces_are_known_artifacts():
    for m in load_all_manifests().values():
        for artifact in (*m.requires, *m.optional, *m.produces):
            assert isinstance(artifact, Artifact)


# --------------------------------------------------------------------------- #
# Graph validation                                                            #
# --------------------------------------------------------------------------- #


def test_documented_graph_validates():
    validate_manifest_graph(load_all_manifests())


def test_producer_of_resolves_documented_producers():
    manifests = load_all_manifests()
    assert producer_of(Artifact.SPENDING_REPORT, manifests) == "spending-analysis"
    assert producer_of(Artifact.ACTIVE_IPS, manifests) == "goals-onboarding"
    assert producer_of(Artifact.DRIFT_REPORT, manifests) == "portfolio-analysis"
    assert producer_of(Artifact.RESEARCH_BRIEFS, manifests) == "research"
    assert producer_of(Artifact.PROPOSED_ACTION, manifests) == "action-drafting"
    assert producer_of(Artifact.REVIEWER_VERDICT, manifests) == "reviewer"
    # Preloaded/external inputs have no producing skill.
    assert producer_of(Artifact.HOLDINGS, manifests) is None


def _manifest(**overrides) -> SkillManifest:
    base = dict(id="x", summary="s", applies_when="w", parallelizable=True)
    base.update(overrides)
    return SkillManifest.model_validate(base)


def test_graph_rejects_unsatisfiable_requirement():
    # `drift_report` requires a producer; without portfolio-analysis it dangles.
    manifests = {"action-drafting": _manifest(id="action-drafting", requires=["drift_report"])}
    with pytest.raises(SkillManifestError, match="which no skill produces"):
        validate_manifest_graph(manifests)


def test_graph_allows_preloaded_requirement_without_producer():
    manifests = {"portfolio-analysis": _manifest(id="portfolio-analysis", requires=["holdings"])}
    validate_manifest_graph(manifests)  # holdings is a recognized preloaded input


def test_graph_rejects_ambiguous_producer():
    manifests = {
        "a": _manifest(id="a", produces=["drift_report"]),
        "b": _manifest(id="b", produces=["drift_report"]),
    }
    with pytest.raises(SkillManifestError, match="produced by both"):
        validate_manifest_graph(manifests)


def test_graph_rejects_mandatory_if_on_unproduced_artifact():
    manifests = {"reviewer": _manifest(id="reviewer", mandatory_if="proposed_action exists")}
    with pytest.raises(SkillManifestError, match="which no skill produces"):
        validate_manifest_graph(manifests)


# --------------------------------------------------------------------------- #
# Field-level schema behaviour                                                #
# --------------------------------------------------------------------------- #


def test_unknown_artifact_rejected():
    with pytest.raises(Exception):
        _manifest(produces=["not_a_real_artifact"])


def test_mandatory_if_parsed_from_string():
    m = _manifest(mandatory_if="proposed_action exists")
    assert isinstance(m.mandatory_if, MandatoryIf)
    assert m.mandatory_if.artifact == Artifact.PROPOSED_ACTION
    assert str(m.mandatory_if) == "proposed_action exists"


def test_mandatory_if_satisfied():
    trigger = _manifest(mandatory_if="proposed_action exists").mandatory_if
    assert trigger.satisfied({"proposed_action", "holdings"})
    assert not trigger.satisfied({"holdings"})


def test_mandatory_if_bad_grammar_rejected():
    with pytest.raises(Exception, match="mandatory_if"):
        _manifest(mandatory_if="proposed_action was_reviewed")


def test_self_dependency_rejected():
    with pytest.raises(Exception, match="requires and produces"):
        _manifest(requires=["drift_report"], produces=["drift_report"])


def test_unknown_field_rejected():
    # extra="forbid" catches front-matter typos (e.g. `require:` for `requires:`).
    with pytest.raises(Exception):
        _manifest(require=["drift_report"])


# --------------------------------------------------------------------------- #
# Loader failure modes & startup verification                                 #
# --------------------------------------------------------------------------- #


def test_load_manifest_missing_skill_raises():
    with pytest.raises(SkillManifestError, match="Could not locate SKILL.md"):
        load_manifest("does-not-exist")


def test_verify_all_manifests_success():
    verify_all_manifests()


def test_verify_all_manifests_missing_block_raises(tmp_path, monkeypatch):
    skill_dir = tmp_path / "brokenskill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: brokenskill\nmetadata:\n  version: '0.1.0'\n---\n# body\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SKILLS_DIR", str(tmp_path))
    with pytest.raises(SkillManifestError, match="no 'manifest:' front-matter block"):
        verify_all_manifests(skill_names=["brokenskill"])


def test_verify_all_manifests_registry_mode_skips(monkeypatch):
    # No local SKILL.md files (container/registry deployment): verification is a no-op.
    monkeypatch.delenv("SKILLS_DIR", raising=False)
    monkeypatch.setattr("orchestrator.skills.manifest._find_skill_md", lambda name: None)
    verify_all_manifests(skill_names=["research", "reviewer"])
