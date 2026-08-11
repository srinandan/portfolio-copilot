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
    emit_action_executed_audit,
    emit_action_failed_audit,
)


@pytest.fixture
def sample_proposed_action():
    return ProposedAction(
        action_id="act_exec_123",
        session_id="sess_exec_1",
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


def test_emit_action_executed_audit_writes_entry(sample_proposed_action):
    mock_client = MagicMock()

    emit_action_executed_audit(
        sample_proposed_action,
        broker_order_id="broker-ord-555",
        executing_user_id="user-exec-1",
        db_client=mock_client,
    )

    mock_client.append_audit_log.assert_called_once()
    audit_entry = mock_client.append_audit_log.call_args[0][0]
    assert audit_entry.event_type == EventType.ACTION_EXECUTED
    assert audit_entry.related_action_id == "act_exec_123"
    assert audit_entry.actor.type == ActorType.AGENT
    assert audit_entry.actor.skill_name == "orchestrator-execution-gate"
    assert audit_entry.actor.skill_version == "0.1.0"
    assert audit_entry.actor.registry_entry_id is None
    assert audit_entry.actor.approval_scope is None
    assert "broker-ord-555" in audit_entry.detail
    assert "user-exec-1" in audit_entry.detail


def test_emit_action_failed_audit_writes_entry(sample_proposed_action):
    mock_client = MagicMock()

    emit_action_failed_audit(
        sample_proposed_action,
        error="insufficient funds",
        db_client=mock_client,
    )

    mock_client.append_audit_log.assert_called_once()
    audit_entry = mock_client.append_audit_log.call_args[0][0]
    assert audit_entry.event_type == EventType.ACTION_FAILED
    assert audit_entry.related_action_id == "act_exec_123"
    assert audit_entry.actor.type == ActorType.AGENT
    assert audit_entry.actor.skill_name == "orchestrator-execution-gate"
    assert audit_entry.actor.skill_version == "0.1.0"
    assert audit_entry.actor.registry_entry_id is None
    assert audit_entry.actor.approval_scope is None
    assert "insufficient funds" in audit_entry.detail


def test_execution_gate_uses_orchestrator_build_sha(sample_proposed_action, monkeypatch):
    mock_client = MagicMock()
    monkeypatch.setenv("ORCHESTRATOR_BUILD_SHA", "sha-exec-987654")

    emit_action_executed_audit(
        sample_proposed_action,
        broker_order_id="broker-1",
        db_client=mock_client,
    )
    audit_entry = mock_client.append_audit_log.call_args[0][0]
    assert audit_entry.actor.skill_version == "sha-exec-987654"
    assert audit_entry.actor.registry_entry_id is None
    assert audit_entry.actor.approval_scope is None


@pytest.mark.parametrize(
    "emitter, kwargs",
    [
        (
            emit_action_executed_audit,
            {"broker_order_id": "ord-1", "executing_user_id": "u1"},
        ),
        (emit_action_failed_audit, {"error": "bad order"}),
    ],
)
def test_emit_action_fails_closed_on_audit_write_error(sample_proposed_action, emitter, kwargs):
    mock_client = MagicMock()
    mock_client.append_audit_log.side_effect = Exception("Firestore down")

    with pytest.raises(RuntimeError, match="Audit log write failed for action"):
        emitter(sample_proposed_action, **kwargs, db_client=mock_client)
