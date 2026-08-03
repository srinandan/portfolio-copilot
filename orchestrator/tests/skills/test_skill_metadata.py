"""Tests for shared skill metadata helper."""

from orchestrator.skills._skill_metadata import read_skill_version


def test_read_skill_version():
    # Test reading valid skills
    version_goals = read_skill_version("goals-onboarding")
    assert version_goals == "0.2.0"

    version_action = read_skill_version("action-drafting")
    assert version_action == "0.1.0"

    version_pa = read_skill_version("portfolio-analysis")
    assert version_pa == "0.1.0"

    # Test non-existent skill falls back to 0.1.0
    version_fake = read_skill_version("non-existent-skill")
    assert version_fake == "0.1.0"
