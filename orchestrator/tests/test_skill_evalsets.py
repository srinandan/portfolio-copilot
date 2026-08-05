"""Tests for ADK EvalSet definitions and doc-only agent evaluation."""

from pathlib import Path

import pytest
from evals.doc_only_agent import build_doc_only_agent
from evals.runner import load_skill_evalset
from google.adk.evaluation.eval_set import EvalSet

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
ALL_SKILLS = [
    "goals-onboarding",
    "portfolio-analysis",
    "action-drafting",
    "spending-analysis",
    "research",
    "reviewer",
]


@pytest.mark.parametrize("skill_name", ALL_SKILLS)
def test_skill_evalset_validity(skill_name: str):
    """Verifies that each skill has a valid .evalset.json conforming to ADK EvalSet."""
    skill_dir = SKILLS_DIR / skill_name
    json_files = list(skill_dir.glob("*.evalset.json"))
    assert len(json_files) == 1, f"Expected 1 .evalset.json in {skill_dir}, found {len(json_files)}"

    eval_set_path = json_files[0]
    eval_set = EvalSet.model_validate_json(eval_set_path.read_text(encoding="utf-8"))

    assert eval_set.eval_set_id == skill_name
    assert len(eval_set.eval_cases) >= 4, f"Expected at least 4 test cases for {skill_name}"

    for case in eval_set.eval_cases:
        assert case.eval_id, f"Missing eval_id in case for {skill_name}"
        assert case.conversation and len(case.conversation) >= 1
        invocation = case.conversation[0]
        assert invocation.user_content and len(invocation.user_content.parts) >= 1
        assert invocation.user_content.parts[0].text, "Missing user prompt text"
        assert invocation.final_response and len(invocation.final_response.parts) >= 1
        assert invocation.final_response.parts[0].text, "Missing expected final response text"


@pytest.mark.parametrize("skill_name", ALL_SKILLS)
def test_skill_no_legacy_txtpb(skill_name: str):
    """Ensures legacy EVAL.txtpb files have been removed."""
    txtpb_file = SKILLS_DIR / skill_name / "EVAL.txtpb"
    assert not txtpb_file.exists(), f"Found legacy {txtpb_file}; should be removed"


@pytest.mark.parametrize("skill_name", ALL_SKILLS)
def test_build_doc_only_agent(skill_name: str):
    """Tests that doc-only agent builder constructs an LlmAgent with SKILL.md and no tools."""
    skill_dir = SKILLS_DIR / skill_name
    agent = build_doc_only_agent(skill_dir)

    assert agent.name.startswith("doc_only_")
    assert agent.tools == [] or agent.tools is None
    expected_doc = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    assert agent.instruction == expected_doc


def test_build_doc_only_agent_missing_dir():
    """Verifies proper error handling when skill dir does not exist."""
    with pytest.raises(FileNotFoundError):
        build_doc_only_agent(SKILLS_DIR / "nonexistent_skill_dir_xyz")


def test_load_skill_evalset_helper():
    """Tests load_skill_evalset helper with valid and invalid paths."""
    eval_set = load_skill_evalset(SKILLS_DIR / "goals-onboarding")
    assert eval_set.eval_set_id == "goals-onboarding"

    with pytest.raises(FileNotFoundError):
        load_skill_evalset(REPO_ROOT / "docs")


def test_eval_runner_heuristic_mode_without_api_key(monkeypatch):
    """Verifies that running without an API key executes in heuristic mode without false failure."""
    from evals.runner import run_doc_only_eval

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = run_doc_only_eval(SKILLS_DIR / "goals-onboarding", use_llm_judge=False)

    assert result.status == "PASS"
    assert result.mode == "heuristic"
    assert result.score is not None
    assert result.total_cases > 0


def test_eval_runner_llm_judge_skipped_without_api_key(monkeypatch):
    """Verifies that requesting LLM judge without GEMINI_API_KEY marks run as SKIPPED_NO_KEY with None score."""
    from evals.runner import run_doc_only_eval

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = run_doc_only_eval(SKILLS_DIR / "goals-onboarding", use_llm_judge=True)

    assert result.status == "SKIPPED_NO_KEY"
    assert result.mode == "llm_judge"
    assert result.score is None


def test_report_generation_warning_banner_without_api_key(monkeypatch):
    """Verifies that markdown report renders a clear warning banner when API key is missing."""
    from evals.report import evaluate_skills, generate_markdown_report

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    reports = evaluate_skills(SKILLS_DIR, use_llm_judge=False)
    md_report = generate_markdown_report(reports, use_llm_judge=False)

    assert "⚠️" in md_report
    assert "evaluated heuristically; LLM judge skipped" in md_report
    assert "🔍 Heuristic" in md_report
