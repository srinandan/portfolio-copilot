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
from orchestrator.state.writers import (
    emit_approval_granted_audit,
    emit_approval_rejected_audit,
    emit_approval_requested_audit,
)


@pytest.fixture
def sample_proposed_action():
    return ProposedAction(
        action_id="act_123",
        session_id="sess_1",
        type=ActionType.TRADE,
        ticker="VTI",
        side=Side.BUY,
        quantity=10.0,
        order_type=OrderType.MARKET,
        estimated_price_usd=250.0,
        estimated_value_usd=2500.0,
        rationale="Rebalancing into equity per IPS target.",
        supporting_research_refs=[],
        ips_version_referenced=RelatedIPSVersion(ips_id="ips_1", version=1),
        proposed_by_skill_version=SkillVersionRef(skill_name="private-action-drafting", skill_version="0.2.0"),
        status=ActionStatus.DRAFTED,
        created_at=datetime.now(timezone.utc),
    )


def test_emit_approval_requested_audit_writes_entry(sample_proposed_action):
    mock_client = MagicMock()

    emit_approval_requested_audit(
        sample_proposed_action,
        reviewer_verdict_id="verdict_99",
        db_client=mock_client,
    )

    mock_client.append_audit_log.assert_called_once()
    audit_entry = mock_client.append_audit_log.call_args[0][0]
    assert audit_entry.event_type == EventType.APPROVAL_REQUESTED
    assert audit_entry.related_action_id == "act_123"
    assert audit_entry.actor.type == ActorType.AGENT
    assert "verdict_99" in audit_entry.detail


def test_emit_approval_granted_audit_uses_human_actor(sample_proposed_action):
    mock_client = MagicMock()

    emit_approval_granted_audit(
        sample_proposed_action,
        approving_user_id="user_approve",
        edit_rounds=2,
        db_client=mock_client,
    )

    mock_client.append_audit_log.assert_called_once()
    audit_entry = mock_client.append_audit_log.call_args[0][0]
    assert audit_entry.event_type == EventType.APPROVAL_GRANTED
    assert audit_entry.related_action_id == "act_123"
    assert audit_entry.actor.type == ActorType.HUMAN
    assert audit_entry.actor.user_id == "user_approve"


def test_emit_approval_rejected_audit_agent_actor_when_no_user_id(
    sample_proposed_action,
):
    # Test 1: No rejecting_user_id -> AGENT actor
    mock_client1 = MagicMock()
    emit_approval_rejected_audit(
        sample_proposed_action,
        reason="auto limit exceeded",
        rejecting_user_id=None,
        db_client=mock_client1,
    )
    mock_client1.append_audit_log.assert_called_once()
    audit1 = mock_client1.append_audit_log.call_args[0][0]
    assert audit1.event_type == EventType.APPROVAL_REJECTED
    assert audit1.actor.type == ActorType.AGENT
    assert audit1.actor.skill_name == "orchestrator-hitl-gate"

    # Test 2: With rejecting_user_id -> HUMAN actor
    mock_client2 = MagicMock()
    emit_approval_rejected_audit(
        sample_proposed_action,
        reason="too risky",
        rejecting_user_id="user_reject",
        db_client=mock_client2,
    )
    mock_client2.append_audit_log.assert_called_once()
    audit2 = mock_client2.append_audit_log.call_args[0][0]
    assert audit2.event_type == EventType.APPROVAL_REJECTED
    assert audit2.actor.type == ActorType.HUMAN
    assert audit2.actor.user_id == "user_reject"


@pytest.mark.parametrize(
    "emitter, kwargs",
    [
        (emit_approval_requested_audit, {}),
        (emit_approval_granted_audit, {"approving_user_id": "u1"}),
        (emit_approval_rejected_audit, {"reason": "bad"}),
    ],
)
def test_emit_approval_fails_closed_on_audit_write_error(
    sample_proposed_action, emitter, kwargs
):
    mock_client = MagicMock()
    mock_client.append_audit_log.side_effect = Exception("Firestore down")

    with pytest.raises(RuntimeError, match="Audit log write failed for approval"):
        emitter(sample_proposed_action, **kwargs, db_client=mock_client)
