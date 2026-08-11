"""Unit tests for Reviewer audit writer."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from orchestrator.contracts.audit_log import ActorType, EventType
from orchestrator.contracts.ips import RelatedIPSVersion
from orchestrator.contracts.proposed_action import (
    ActionStatus,
    ActionType,
    OrderType,
    ProposedAction,
    Side,
    SkillVersionRef,
)
from orchestrator.contracts.reviewer_verdict import ReviewerVerdict, RuleResult
from orchestrator.state.writers import emit_review_completed_audit


@pytest.fixture
def sample_proposed_action() -> ProposedAction:
    return ProposedAction(
        action_id="act_rev_1",
        session_id="sess_rev",
        type=ActionType.TRADE,
        ticker="AAPL",
        side=Side.BUY,
        quantity=10.0,
        order_type=OrderType.MARKET,
        estimated_price_usd=200.0,
        estimated_value_usd=2000.0,
        rationale="Trade rationale",
        supporting_research_refs=[],
        ips_version_referenced=RelatedIPSVersion(ips_id="ips_1", version=1),
        proposed_by_skill_version=SkillVersionRef(skill_name="private-action-drafting", skill_version="0.1.0"),
        status=ActionStatus.DRAFTED,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_passing_verdict() -> ReviewerVerdict:
    return ReviewerVerdict(
        verdict_id="v_pass",
        action_id="act_rev_1",
        ips_version_checked_against=RelatedIPSVersion(ips_id="ips_1", version=1),
        rule_results=[RuleResult(rule_id="excluded_ticker", description="test", passed=True)],
        overall_pass=True,
        requires_human_approval=False,
        reviewer_skill_version=SkillVersionRef(skill_name="private-reviewer", skill_version="0.1.0"),
        reviewed_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_failing_verdict() -> ReviewerVerdict:
    return ReviewerVerdict(
        verdict_id="v_fail",
        action_id="act_rev_1",
        ips_version_checked_against=RelatedIPSVersion(ips_id="ips_1", version=1),
        rule_results=[
            RuleResult(
                rule_id="excluded_ticker",
                description="test",
                passed=False,
                detail="TSLA excluded",
            )
        ],
        overall_pass=False,
        requires_human_approval=True,
        reviewer_skill_version=SkillVersionRef(skill_name="private-reviewer", skill_version="0.1.0"),
        reviewed_at=datetime.now(timezone.utc),
    )


def test_emit_review_completed_audit_writes_entry_all_pass(sample_proposed_action, sample_passing_verdict):
    mock_client = MagicMock()
    emit_review_completed_audit(
        sample_proposed_action,
        authoritative_verdict=sample_passing_verdict,
        llm_verdict=sample_passing_verdict,
        registry_entry_id="projects/test/revisions/rev-rev-1",
        db_client=mock_client,
    )

    mock_client.append_audit_log.assert_called_once()
    audit_entry = mock_client.append_audit_log.call_args[0][0]
    assert audit_entry.event_type == EventType.REVIEW_COMPLETED
    assert audit_entry.related_action_id == "act_rev_1"
    assert audit_entry.actor.type == ActorType.AGENT
    assert audit_entry.actor.skill_name == "private-reviewer"
    assert audit_entry.actor.registry_entry_id == "projects/test/revisions/rev-rev-1"
    assert audit_entry.actor.approval_scope == "read:proposed_action,read:holdings,read:ips"
    assert "all rules passed" in audit_entry.detail
    assert "divergence" not in audit_entry.detail


def test_emit_review_completed_audit_captures_failing_rules(sample_proposed_action, sample_failing_verdict):
    mock_client = MagicMock()
    emit_review_completed_audit(
        sample_proposed_action,
        authoritative_verdict=sample_failing_verdict,
        llm_verdict=sample_failing_verdict,
        db_client=mock_client,
    )

    mock_client.append_audit_log.assert_called_once()
    audit_entry = mock_client.append_audit_log.call_args[0][0]
    assert "failed rules: ['excluded_ticker']" in audit_entry.detail


def test_emit_review_completed_audit_captures_divergence(
    sample_proposed_action, sample_passing_verdict, sample_failing_verdict
):
    mock_client = MagicMock()
    # LLM says pass, deterministic says fail -> divergence!
    emit_review_completed_audit(
        sample_proposed_action,
        authoritative_verdict=sample_failing_verdict,
        llm_verdict=sample_passing_verdict,
        db_client=mock_client,
    )

    mock_client.append_audit_log.assert_called_once()
    audit_entry = mock_client.append_audit_log.call_args[0][0]
    assert "LLM/deterministic divergence" in audit_entry.detail
    assert (
        "LLM verdict overall_pass=True disagreed with deterministic re-check overall_pass=False" in audit_entry.detail
    )


def test_emit_review_completed_audit_no_llm_verdict(sample_proposed_action, sample_passing_verdict):
    mock_client = MagicMock()
    emit_review_completed_audit(
        sample_proposed_action,
        authoritative_verdict=sample_passing_verdict,
        llm_verdict=None,
        db_client=mock_client,
    )

    mock_client.append_audit_log.assert_called_once()
    audit_entry = mock_client.append_audit_log.call_args[0][0]
    assert "divergence" not in audit_entry.detail


def test_emit_review_completed_audit_fails_closed(sample_proposed_action, sample_passing_verdict):
    mock_client = MagicMock()
    mock_client.append_audit_log.side_effect = Exception("Firestore down")

    with pytest.raises(RuntimeError, match="Audit log write failed for review completion"):
        emit_review_completed_audit(
            sample_proposed_action,
            authoritative_verdict=sample_passing_verdict,
            llm_verdict=sample_passing_verdict,
            db_client=mock_client,
        )
