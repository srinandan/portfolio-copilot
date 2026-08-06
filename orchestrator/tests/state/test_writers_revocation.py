"""Unit tests for SKILL_REVOKED audit log writer."""

from unittest.mock import MagicMock

import pytest

from orchestrator.contracts.audit_log import ActorType, EventType
from orchestrator.state.writers import emit_skill_revoked_audit


def test_emit_skill_revoked_audit_writes_entry():
    mock_client = MagicMock()
    emit_skill_revoked_audit(
        revoked_skill_short_name="research",
        prior_registry_entry_id="projects/test/revisions/rev-research-1",
        detail="Observed missing on planning cycle",
        db_client=mock_client,
    )

    mock_client.append_audit_log.assert_called_once()
    entry = mock_client.append_audit_log.call_args[0][0]
    assert entry.event_type == EventType.SKILL_REVOKED
    assert entry.actor.type == ActorType.AGENT
    assert entry.actor.skill_name == "private-research"
    assert entry.actor.registry_entry_id == "projects/test/revisions/rev-research-1"
    assert entry.actor.approval_scope == "read:external_market_data"
    assert "Observed missing on planning cycle" in entry.detail


@pytest.mark.parametrize("skill_name", ["research", "private-research"])
def test_emit_skill_revoked_uses_short_or_prefixed_name(skill_name):
    mock_client = MagicMock()
    emit_skill_revoked_audit(
        revoked_skill_short_name=skill_name,
        prior_registry_entry_id="rev-1",
        db_client=mock_client,
    )
    entry = mock_client.append_audit_log.call_args[0][0]
    assert entry.actor.skill_name == "private-research"


def test_emit_skill_revoked_fails_closed_on_audit_write_error():
    mock_client = MagicMock()
    mock_client.append_audit_log.side_effect = Exception("Firestore down")

    with pytest.raises(RuntimeError, match="Audit log write failed for skill revocation"):
        emit_skill_revoked_audit(
            revoked_skill_short_name="research",
            db_client=mock_client,
        )
