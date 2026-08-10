from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.orchestrator.contracts import (
    Constraints,
    HoldingsSnapshot,
    InvestmentPolicyStatement,
    IPSStatus,
    Position,
    RiskTolerance,
    TargetAllocation,
)
from src.orchestrator.data.firestore import FirestoreClient


def test_pydantic_dict_factory():
    with patch("google.cloud.firestore.Client"):
        client = FirestoreClient(project="test-project")

        ips = InvestmentPolicyStatement(
            ips_id="user123_ips",
            user_id="user123",
            version=1,
            status=IPSStatus.ACTIVE,
            effective_date="2026-01-01",
            risk_tolerance=RiskTolerance.MODERATE,
            time_horizon_years=10,
            target_allocation=[
                TargetAllocation(asset_class="equity", target_percent=60, min_percent=50, max_percent=70),
            ],
            constraints=Constraints(concentration_limit_percent=15),
            created_at=datetime.now(timezone.utc),
        )

        raw_dict = client._dict_factory(ips)
        assert "ips_id" in raw_dict
        assert raw_dict["status"] == "active"

        parsed_ips = InvestmentPolicyStatement.model_validate(raw_dict)
        assert parsed_ips.ips_id == ips.ips_id


def test_firestore_client_initialization_no_emulator():
    with patch("google.cloud.firestore.Client") as mock_client:
        client = FirestoreClient(project="test-project")
        mock_client.assert_called_once_with(project="test-project")


def test_set_liabilities():
    with patch("google.cloud.firestore.Client"):
        client = FirestoreClient(project="test-project")
        client.db = MagicMock()
        mock_doc_ref = MagicMock()
        client.db.collection.return_value.document.return_value = mock_doc_ref

        from src.orchestrator.contracts import (
            LiabilitiesSnapshot,
            Liability,
            LiabilityType,
        )

        snapshot = LiabilitiesSnapshot(
            user_id="u1",
            as_of=datetime.now(timezone.utc),
            liabilities=[
                Liability(liability_id="l1", type=LiabilityType.MORTGAGE, balance_usd=100000, minimum_payment_usd=1000)
            ],
        )

        client.set_liabilities("u1", snapshot)
        mock_doc_ref.set.assert_called_once()


def test_firestore_client_read_ops():
    with patch("google.cloud.firestore.Client"):
        client = FirestoreClient(project="test-project")
        client.db = MagicMock()

        # get_liabilities empty
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value.exists = False
        client.db.collection.return_value.document.return_value = mock_doc_ref
        assert client.get_liabilities("u1") is None

        # get_active_ips empty
        mock_query = MagicMock()
        mock_query.stream.return_value = []
        client.db.collection.return_value.where.return_value.where.return_value.limit.return_value = mock_query
        assert client.get_active_ips("ips1") is None


def test_update_ips_transactional_error_multiple_active():
    with patch("google.cloud.firestore.Client"):
        client = FirestoreClient(project="test-project")

        ips = InvestmentPolicyStatement(
            ips_id="user123_ips",
            user_id="user123",
            version=1,
            status=IPSStatus.ACTIVE,
            effective_date="2026-01-01",
            risk_tolerance=RiskTolerance.MODERATE,
            time_horizon_years=10,
            target_allocation=[],
            constraints=Constraints(concentration_limit_percent=15),
            created_at=datetime.now(timezone.utc),
        )

        transaction = MagicMock()

        original_func = client._update_ips_transactional.to_wrap

        bad_ips = ips.model_copy()
        bad_ips.status = IPSStatus.DRAFT
        with pytest.raises(ValueError, match="must have status 'active'"):
            original_func(client, transaction, bad_ips)

        client.db = MagicMock()
        mock_query = MagicMock()
        mock_query.stream.return_value = [MagicMock(), MagicMock()]
        client.db.collection.return_value.where.return_value.where.return_value.limit.return_value = mock_query

        with pytest.raises(ValueError, match="invariant violated"):
            original_func(client, transaction, ips)


def test_update_ips_transactional_error_version_not_1():
    with patch("google.cloud.firestore.Client"):
        client = FirestoreClient(project="test-project")
        client.db = MagicMock()

        ips = InvestmentPolicyStatement(
            ips_id="user123_ips",
            user_id="user123",
            version=2,
            status=IPSStatus.ACTIVE,
            effective_date="2026-01-01",
            risk_tolerance=RiskTolerance.MODERATE,
            time_horizon_years=10,
            target_allocation=[],
            constraints=Constraints(concentration_limit_percent=15),
            created_at=datetime.now(timezone.utc),
        )

        transaction = MagicMock()
        mock_query = MagicMock()
        mock_query.stream.return_value = []
        client.db.collection.return_value.where.return_value.where.return_value.limit.return_value = mock_query

        original_func = client._update_ips_transactional.to_wrap

        with pytest.raises(ValueError, match="new version is not 1"):
            original_func(client, transaction, ips)


def test_update_ips_transactional_success_update():
    with patch("google.cloud.firestore.Client"):
        client = FirestoreClient(project="test-project")
        client.db = MagicMock()

        ips = InvestmentPolicyStatement(
            ips_id="user123_ips",
            user_id="user123",
            version=2,
            status=IPSStatus.ACTIVE,
            effective_date="2026-01-01",
            risk_tolerance=RiskTolerance.MODERATE,
            time_horizon_years=10,
            target_allocation=[],
            constraints=Constraints(concentration_limit_percent=15),
            created_at=datetime.now(timezone.utc),
        )

        transaction = MagicMock()

        mock_query = MagicMock()
        mock_old_doc = MagicMock()
        old_data = ips.model_dump(mode="json")
        old_data["version"] = 1
        mock_old_doc.to_dict.return_value = old_data

        mock_query.stream.return_value = [mock_old_doc]
        client.db.collection.return_value.where.return_value.where.return_value.limit.return_value = mock_query

        original_func = client._update_ips_transactional.to_wrap
        original_func(client, transaction, ips)

        assert transaction.set.call_count == 2


@patch("google.cloud.firestore.Client")
def test_get_holdings(mock_client):
    client = FirestoreClient("test-project")

    mock_db = MagicMock()
    mock_doc_ref = MagicMock()
    mock_doc = MagicMock()

    mock_doc.exists = True
    now = datetime.now(timezone.utc)
    mock_doc.to_dict.return_value = {
        "user_id": "user1",
        "as_of": now.isoformat(),
        "positions": [],
        "cash_usd": 1000.0,
        "total_value_usd": 1000.0,
    }

    mock_doc_ref.get.return_value = mock_doc
    mock_db.collection.return_value.document.return_value = mock_doc_ref
    client.db = mock_db

    holdings = client.get_holdings("user1")
    assert holdings is not None
    assert holdings.user_id == "user1"
    assert holdings.cash_usd == 1000.0


@patch("google.cloud.firestore.Client")
def test_set_holdings(mock_client):
    client = FirestoreClient("test-project")

    mock_db = MagicMock()
    mock_doc_ref = MagicMock()

    mock_db.collection.return_value.document.return_value = mock_doc_ref
    client.db = mock_db

    now = datetime.now(timezone.utc)
    holdings = HoldingsSnapshot(
        user_id="user1",
        as_of=now,
        positions=[Position(ticker="AAPL", quantity=10, asset_class="equity", market_value_usd=1500)],
        cash_usd=500.0,
    )

    client.set_holdings("user1", holdings)

    mock_doc_ref.set.assert_called_once()
    called_args = mock_doc_ref.set.call_args[0][0]
    assert called_args["user_id"] == "user1"
    assert called_args["cash_usd"] == 500.0


@patch('google.cloud.firestore.Client')
def test_get_active_ips_by_user_single(mock_client):
    """Verifies get_active_ips_by_user returns active IPS when exactly one active document exists."""
    client = FirestoreClient("test-project")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_doc = MagicMock()

    mock_doc.to_dict.return_value = {
        "ips_id": "ips_user1",
        "user_id": "user1",
        "version": 1,
        "status": "active",
        "effective_date": "2026-01-01",
        "risk_tolerance": "moderate",
        "time_horizon_years": 10,
        "target_allocation": [{"asset_class": "equity", "target_percent": 60.0, "min_percent": 50.0, "max_percent": 70.0}],
        "constraints": {"concentration_limit_percent": 15},
        "created_at": "2026-01-01T00:00:00Z",
    }
    mock_query.stream.return_value = [mock_doc]
    mock_db.collection.return_value.where.return_value.where.return_value = mock_query
    client.db = mock_db

    ips = client.get_active_ips_by_user("user1")
    assert ips is not None
    assert ips.ips_id == "ips_user1"
    assert ips.user_id == "user1"


@patch('google.cloud.firestore.Client')
def test_get_active_ips_by_user_none(mock_client):
    """Verifies get_active_ips_by_user returns None when no active IPS exists."""
    client = FirestoreClient("test-project")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_query.stream.return_value = []
    mock_db.collection.return_value.where.return_value.where.return_value = mock_query
    client.db = mock_db

    ips = client.get_active_ips_by_user("user1")
    assert ips is None


@patch('google.cloud.firestore.Client')
def test_get_active_ips_by_user_multiple_invariant_violation(mock_client):
    """Verifies D2: get_active_ips_by_user raises ValueError if multiple active documents exist."""
    client = FirestoreClient("test-project")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_doc1 = MagicMock()
    mock_doc2 = MagicMock()
    mock_query.stream.return_value = [mock_doc1, mock_doc2]
    mock_db.collection.return_value.where.return_value.where.return_value = mock_query
    client.db = mock_db

    with pytest.raises(ValueError, match="invariant violated: found multiple active IPS documents"):
        client.get_active_ips_by_user("user1")


def test_proposed_action_roundtrip_with_broker_order_id():
    with patch("google.cloud.firestore.Client"):
        client = FirestoreClient(project="test-project")
        client.db = MagicMock()

        from src.orchestrator.contracts.ips import RelatedIPSVersion
        from src.orchestrator.contracts.proposed_action import (
            ActionStatus,
            ActionType,
            OrderType,
            ProposedAction,
            Side,
            SkillVersionRef,
        )

        action = ProposedAction(
            action_id="act_123",
            session_id="sess_123",
            type=ActionType.TRADE,
            ticker="GOOG",
            side=Side.BUY,
            quantity=10.0,
            order_type=OrderType.MARKET,
            estimated_price_usd=150.0,
            estimated_value_usd=1500.0,
            rationale="Rebalance",
            ips_version_referenced=RelatedIPSVersion(ips_id="ips_1", version=1),
            proposed_by_skill_version=SkillVersionRef(skill_name="test-skill", skill_version="1.0.0"),
            status=ActionStatus.EXECUTED,
            created_at=datetime.now(timezone.utc),
            broker_order_id="broker_ord_999",
        )

        mock_doc_ref = MagicMock()
        client.db.collection.return_value.document.return_value = mock_doc_ref
        client.set_proposed_action(action)
        written_dict = mock_doc_ref.set.call_args[0][0]
        assert written_dict["broker_order_id"] == "broker_ord_999"

        mock_doc_ref.get.return_value.exists = True
        mock_doc_ref.get.return_value.to_dict.return_value = written_dict
        loaded_action = client.get_proposed_action("act_123")
        assert loaded_action is not None
        assert loaded_action.broker_order_id == "broker_ord_999"

