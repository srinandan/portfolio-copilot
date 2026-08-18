"""Tests for the retrieval interface (ADR-0022, Phase 3b)."""

from orchestrator.planning import DEFAULT_RETRIEVER, ListAllRetriever, Retriever, SkillCandidate
from orchestrator.skills.manifest import load_all_manifests


def test_list_all_returns_a_candidate_per_authorized_skill():
    manifests = load_all_manifests()
    candidates = ListAllRetriever().retrieve("anything", manifests)
    assert {c.id for c in candidates} == set(manifests)
    assert all(isinstance(c, SkillCandidate) for c in candidates)


def test_candidate_carries_manifest_text():
    manifests = load_all_manifests()
    by_id = {c.id: c for c in ListAllRetriever().retrieve("q", manifests)}
    assert by_id["reviewer"].summary == manifests["reviewer"].summary
    assert by_id["reviewer"].applies_when == manifests["reviewer"].applies_when


def test_list_all_ignores_the_prompt():
    manifests = load_all_manifests()
    a = ListAllRetriever().retrieve("what did I spend?", manifests)
    b = ListAllRetriever().retrieve("sell everything", manifests)
    assert {c.id for c in a} == {c.id for c in b}  # recall-biased: never drops a skill


def test_default_retriever_satisfies_protocol():
    assert isinstance(DEFAULT_RETRIEVER, Retriever)
