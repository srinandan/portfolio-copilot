"""Tests for shared skill metadata helper."""

from orchestrator.skills._skill_metadata import (
    SkillMetadata,
    read_skill_approval_scope,
    read_skill_metadata,
    read_skill_version,
)


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
