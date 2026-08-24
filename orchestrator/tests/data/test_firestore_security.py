"""Security tests for Firestore identifier validation and path traversal prevention."""

from unittest.mock import MagicMock

import pytest

from orchestrator.contracts.holdings import HoldingsSnapshot
from orchestrator.contracts.liabilities import LiabilitiesSnapshot
from orchestrator.data.firestore import FirestoreClient
from orchestrator.managed_agents.dispatcher import _research_cache_key


@pytest.fixture
def mock_firestore_client():
    client = FirestoreClient(project="test-proj", use_mcp=False)
    client.db = MagicMock()
    return client


@pytest.mark.parametrize(
    "bad_user_id",
    [
        "../traversal",
        "user/subcollection/doc",
        "user;DROP",
        "user spaces",
        "a" * 65,
    ],
)
def test_firestore_client_rejects_malformed_user_ids(mock_firestore_client, bad_user_id):
    with pytest.raises(ValueError, match="Invalid user_id format"):
        mock_firestore_client.get_holdings(bad_user_id)

    with pytest.raises(ValueError, match="Invalid user_id format"):
        mock_firestore_client.set_holdings(
            bad_user_id,
            HoldingsSnapshot(user_id="safe_user", as_of="2026-08-24", positions=[]),
        )

    with pytest.raises(ValueError, match="Invalid user_id format"):
        mock_firestore_client.get_liabilities(bad_user_id)

    with pytest.raises(ValueError, match="Invalid user_id format"):
        mock_firestore_client.set_liabilities(
            bad_user_id,
            LiabilitiesSnapshot(user_id="safe_user", as_of="2026-08-24", liabilities=[]),
        )

    with pytest.raises(ValueError, match="Invalid user_id format"):
        mock_firestore_client.get_active_ips_by_user(bad_user_id)

    with pytest.raises(ValueError, match="Invalid user_id format"):
        mock_firestore_client.get_spending_report(bad_user_id)

    with pytest.raises(ValueError, match="Invalid user_id format"):
        mock_firestore_client.get_drift_report(bad_user_id)

    with pytest.raises(ValueError, match="Invalid user_id format"):
        mock_firestore_client.get_user_profile(bad_user_id)


def test_research_cache_key_tenant_isolation():
    q = {"research_question": "Analyze AAPL 10-K filings"}
    key_alice = _research_cache_key(q, user_id="alice")
    key_bob = _research_cache_key(q, user_id="bob")

    assert key_alice == "alice:analyze aapl 10-k filings"
    assert key_bob == "bob:analyze aapl 10-k filings"
    assert key_alice != key_bob


def test_research_cache_key_extracts_user_id_from_dict():
    q = {"query": "NVDA GPU margins", "user_id": "charlie"}
    key = _research_cache_key(q)
    assert key == "charlie:nvda gpu margins"


def test_research_cache_key_invalid_user_id_falls_back_safely():
    q = {"query": "GOOGL earnings", "user_id": "../malicious/path"}
    key = _research_cache_key(q)
    assert key == "anonymous:googl earnings"
