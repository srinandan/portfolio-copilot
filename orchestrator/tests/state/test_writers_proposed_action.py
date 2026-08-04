from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from orchestrator.contracts.audit_log import EventType
from orchestrator.contracts.ips import RelatedIPSVersion
from orchestrator.contracts.proposed_action import (
    ActionStatus,
    ActionType,
    OrderType,
    ProposedAction,
    Side,
    SkillVersionRef,
)
from orchestrator.skills._skill_metadata import read_skill_version
from orchestrator.state.writers import (
    emit_skill_failed_audit,
    emit_skill_invoked_audit,
    write_proposed_action,
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


def test_write_proposed_action_persists_and_audits(sample_proposed_action):
    mock_client = MagicMock()

    result = write_proposed_action(
        user_id="user_123",
        action=sample_proposed_action,
        db_client=mock_client,
    )

    assert result == sample_proposed_action
    mock_client.set_proposed_action.assert_called_once_with(sample_proposed_action)
    mock_client.append_audit_log.assert_called_once()

    audit_entry = mock_client.append_audit_log.call_args[0][0]
    assert audit_entry.event_type == EventType.ACTION_PROPOSED
    assert audit_entry.related_action_id == "act_123"
    assert audit_entry.actor.skill_version == read_skill_version("action-drafting")
    assert audit_entry.actor.skill_name == "private-action-drafting"
    assert audit_entry.actor.approval_scope == "read:holdings,read:ips,read:market_data_quote"


def test_write_proposed_action_carries_registry_entry_id(sample_proposed_action):
    mock_client = MagicMock()
    write_proposed_action(
        user_id="user_123",
        action=sample_proposed_action,
        registry_entry_id="projects/test/revisions/rev-abc",
        db_client=mock_client,
    )
    audit_entry = mock_client.append_audit_log.call_args[0][0]
    assert audit_entry.actor.registry_entry_id == "projects/test/revisions/rev-abc"


def test_write_proposed_action_carries_approval_scope(sample_proposed_action):
    mock_client = MagicMock()
    write_proposed_action(
        user_id="user_123",
        action=sample_proposed_action,
        db_client=mock_client,
    )
    audit_entry = mock_client.append_audit_log.call_args[0][0]
    assert audit_entry.actor.approval_scope == "read:holdings,read:ips,read:market_data_quote"


def test_write_proposed_action_uses_dynamic_skill_version(sample_proposed_action, monkeypatch):
    mock_client = MagicMock()
    monkeypatch.setattr(
        "orchestrator.state.writers.read_skill_version",
        lambda skill_name: "8.8.8",
    )

    write_proposed_action(
        user_id="user_123",
        action=sample_proposed_action,
        db_client=mock_client,
    )

    audit_entry = mock_client.append_audit_log.call_args[0][0]
    assert audit_entry.actor.skill_version == "8.8.8"


def test_write_proposed_action_audit_failure_raises(sample_proposed_action):
    mock_client = MagicMock()
    mock_client.append_audit_log.side_effect = Exception("Firestore audit error")

    with pytest.raises(RuntimeError, match="Audit log write failed for ProposedAction"):
        write_proposed_action(
            user_id="user_123",
            action=sample_proposed_action,
            db_client=mock_client,
        )


def test_emit_skill_invoked_audit_and_failed_audit(monkeypatch):
    mock_client = MagicMock()
    monkeypatch.setattr(
        "orchestrator.state.writers.read_skill_version",
        lambda skill_name: "1.2.3",
    )

    emit_skill_invoked_audit("research", detail="Starting research", db_client=mock_client)
    emit_skill_failed_audit("private-portfolio-analysis", error="No IPS", db_client=mock_client)

    assert mock_client.append_audit_log.call_count == 2

    invoked_entry = mock_client.append_audit_log.call_args_list[0][0][0]
    assert invoked_entry.event_type == EventType.SKILL_INVOKED
    assert invoked_entry.actor.skill_name == "private-research"
    assert invoked_entry.actor.skill_version == "1.2.3"
    assert invoked_entry.detail == "Starting research"

    failed_entry = mock_client.append_audit_log.call_args_list[1][0][0]
    assert failed_entry.event_type == EventType.SKILL_INVOCATION_FAILED
    assert failed_entry.actor.skill_name == "private-portfolio-analysis"
    assert failed_entry.actor.skill_version == "1.2.3"
    assert "No IPS" in failed_entry.detail
