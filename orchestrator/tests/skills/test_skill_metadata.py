"""Tests for shared skill metadata helper."""

import pytest

from orchestrator.skills._skill_metadata import (
    SkillMetadata,
    SkillMetadataError,
    _clean_skill_name,
    read_skill_approval_scope,
    read_skill_metadata,
    read_skill_version,
    verify_all_skills_metadata,
)


def test_clean_skill_name():
    assert _clean_skill_name("private-reviewer") == "reviewer"
    assert _clean_skill_name("projects/foo/skills/private-action-drafting") == "action-drafting"
    assert _clean_skill_name("spending-analysis") == "spending-analysis"


def test_read_skill_version():
    version_goals = read_skill_version("goals-onboarding")
    assert version_goals == "0.2.0"

    version_action = read_skill_version("action-drafting")
    assert version_action == "0.1.0"

    version_pa = read_skill_version("portfolio-analysis")
    assert version_pa == "0.1.0"

    version_fake = read_skill_version("non-existent-skill")
    assert version_fake == "0.1.0"


def test_read_skill_approval_scope_all_registered_skills():
    assert read_skill_approval_scope("goals-onboarding") == "read:holdings,read:liabilities,read:spending,read:ips"
    assert read_skill_approval_scope("action-drafting") == "read:holdings,read:ips,read:market_data_quote"
    assert read_skill_approval_scope("portfolio-analysis") == "read:holdings,read:ips"
    assert read_skill_approval_scope("research") == "read:external_market_data"
    assert read_skill_approval_scope("spending-analysis") == "read:spending,read:holdings"


def test_read_skill_approval_scope_missing_returns_none():
    assert read_skill_approval_scope("non-existent-skill") is None


def test_read_skill_metadata_bundle():
    md = read_skill_metadata("action-drafting")
    assert isinstance(md, SkillMetadata)
    assert md.skill_dir_name == "action-drafting"
    assert md.version == "0.1.0"
    assert md.approval_scope == "read:holdings,read:ips,read:market_data_quote"


def test_verify_all_skills_metadata_success():
    # Should succeed for the full PIPELINE_SKILL_ORDER in the repository layout
    verify_all_skills_metadata()


def test_verify_all_skills_metadata_installed_package_layout(tmp_path, monkeypatch):
    """Simulates an installed-package layout outside the source tree and verifies SKILL.md reachability."""
    isolated_skills_dir = tmp_path / "site-packages" / "orchestrator" / "skills"
    for name in ["research", "reviewer"]:
        skill_dir = isolated_skills_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nmetadata:\n  version: 1.2.3\n---\n- Approval scope: `read:test`\n",
            encoding="utf-8",
        )

    monkeypatch.setenv("SKILLS_DIR", str(isolated_skills_dir))
    verify_all_skills_metadata(skill_names=["research", "private-reviewer"])
    assert read_skill_version("private-reviewer") == "1.2.3"
    assert read_skill_approval_scope("research") == "read:test"


def test_verify_all_skills_metadata_missing_raises(tmp_path, monkeypatch):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.setenv("SKILLS_DIR", str(empty_dir))
    with pytest.raises(SkillMetadataError, match="Startup verification failed: could not locate SKILL.md"):
        verify_all_skills_metadata(skill_names=["research"])
