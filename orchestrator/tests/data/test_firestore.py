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
from src.orchestrator.data.firestore import FirestoreClient, _update_ips_transactional


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

        original_func = _update_ips_transactional.to_wrap

        bad_ips = ips.model_copy()
        bad_ips.status = IPSStatus.DRAFT
        with pytest.raises(ValueError, match="must have status 'active'"):
            original_func(transaction, client.db, bad_ips, client._dict_factory)

        client.db = MagicMock()
        mock_query = MagicMock()
        mock_query.stream.return_value = [MagicMock(), MagicMock()]
        client.db.collection.return_value.where.return_value.where.return_value.limit.return_value = mock_query

        with pytest.raises(ValueError, match="invariant violated"):
            original_func(transaction, client.db, ips, client._dict_factory)


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

        original_func = _update_ips_transactional.to_wrap

        with pytest.raises(ValueError, match="new version is not 1"):
            original_func(transaction, client.db, ips, client._dict_factory)


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

        original_func = _update_ips_transactional.to_wrap
        original_func(transaction, client.db, ips, client._dict_factory)

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


@patch("google.cloud.firestore.Client")
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
        "target_allocation": [
            {"asset_class": "equity", "target_percent": 60.0, "min_percent": 50.0, "max_percent": 70.0}
        ],
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


@patch("google.cloud.firestore.Client")
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


@patch("google.cloud.firestore.Client")
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


def test_set_and_get_spending_report():
    with patch("google.cloud.firestore.Client"):
        client = FirestoreClient(project="test-project")
        client.db = MagicMock()

        mock_doc_ref = MagicMock()
        client.db.collection.return_value.document.return_value = mock_doc_ref

        report_data = {
            "user_id": "user1",
            "total_income_usd": 10000.0,
            "total_outflow_usd": 7000.0,
            "savings_rate": 0.3,
            "reserve_months": 5.0,
            "category_breakdown": [],
            "anomalies": [],
            "narrative_summary": "Test narrative",
        }

        client.set_spending_report("user1", report_data)
        client.db.collection.assert_called_with("spending_reports")
        client.db.collection().document.assert_called_with("user1")
        mock_doc_ref.set.assert_called_with(report_data)

        mock_doc_ref.get.return_value.exists = True
        mock_doc_ref.get.return_value.to_dict.return_value = report_data
        result = client.get_spending_report("user1")
        assert result == report_data

        mock_doc_ref.get.return_value.exists = False
        assert client.get_spending_report("nonexistent") is None


def test_set_and_get_drift_report():
    with patch("google.cloud.firestore.Client"):
        client = FirestoreClient(project="test-project")
        client.db = MagicMock()

        mock_doc_ref = MagicMock()
        client.db.collection.return_value.document.return_value = mock_doc_ref

        drift_data = {
            "user_id": "user1",
            "as_of": "2026-08-01T00:00:00Z",
            "bands": [
                {
                    "asset_class": "Equity",
                    "current_percent": 60.0,
                    "target_percent": 60.0,
                    "min_percent": 50.0,
                    "max_percent": 70.0,
                    "in_band": True,
                    "drift_amount_percent": 0.0,
                }
            ],
            "unclassified_value_usd": 0.0,
            "rebalance_recommended": False,
            "has_active_ips": True,
        }

        client.set_drift_report("user1", drift_data)
        client.db.collection.assert_called_with("drift_reports")
        client.db.collection().document.assert_called_with("user1")
        mock_doc_ref.set.assert_called_with(drift_data)

        mock_doc_ref.get.return_value.exists = True
        mock_doc_ref.get.return_value.to_dict.return_value = drift_data
        result = client.get_drift_report("user1")
        assert result == drift_data

        mock_doc_ref.get.return_value.exists = False
        assert client.get_drift_report("nonexistent") is None


def test_set_and_get_user_profile():
    with patch("google.cloud.firestore.Client"):
        client = FirestoreClient(project="test-project")
        client.db = MagicMock()

        mock_doc_ref = MagicMock()
        client.db.collection.return_value.document.return_value = mock_doc_ref

        profile_data = {
            "user_id": "user1",
            "full_name": "Alex Mercer",
            "email": "alex@example.com",
            "date_of_birth": "1980-06-15",
            "age": 46,
            "marital_status": "married",
            "dependents_count": 2,
            "family_members": [{"name": "Sarah", "relationship": "spouse", "age": 44}],
            "employment_status": "employed",
            "occupation": "Engineer",
            "annual_income_usd": 200000.0,
            "target_retirement_age": 60,
        }

        client.set_user_profile("user1", profile_data)
        client.db.collection.assert_called_with("user_profiles")
        client.db.collection().document.assert_called_with("user1")
        mock_doc_ref.set.assert_called_with(profile_data)

        mock_doc_ref.get.return_value.exists = True
        mock_doc_ref.get.return_value.to_dict.return_value = profile_data
        result = client.get_user_profile("user1")
        assert result == profile_data

        mock_doc_ref.get.return_value.exists = False
        assert client.get_user_profile("nonexistent") is None


def test_firestore_client_mcp_path():
    """Golden path: FirestoreClient executes CRUD via FirestoreMCPClient when use_mcp=True."""
    mock_mcp = MagicMock()
    with patch("google.cloud.firestore.Client"):
        client = FirestoreClient(project="test-project", use_mcp=True)
        client.mcp_client = mock_mcp

        # Holdings
        mock_mcp.get_document.return_value = {
            "user_id": "u1",
            "as_of": "2026-08-01T00:00:00Z",
            "total_value_usd": 1000.0,
            "cash_usd": 100.0,
            "positions": [],
        }
        h = client.get_holdings("u1")
        assert h is not None
        assert h.user_id == "u1"
        mock_mcp.get_document.assert_called_with("holdings", "u1")

        client.set_holdings("u1", h)
        mock_mcp.set_document.assert_called_with("holdings", "u1", client._dict_factory(h))

        # Liabilities
        mock_mcp.get_document.return_value = {
            "user_id": "u1",
            "as_of": "2026-08-01T00:00:00Z",
            "liabilities": [],
        }
        liab = client.get_liabilities("u1")
        assert liab is not None
        mock_mcp.get_document.assert_called_with("liabilities", "u1")

        client.set_liabilities("u1", liab)
        mock_mcp.set_document.assert_called_with("liabilities", "u1", client._dict_factory(liab))

        # Proposed Actions
        from src.orchestrator.contracts import (
            ActionStatus,
            ActionType,
            OrderType,
            ProposedAction,
            RelatedIPSVersion,
            Side,
            SkillVersionRef,
        )

        action = ProposedAction(
            action_id="act_1",
            session_id="sess_1",
            type=ActionType.TRADE,
            ticker="VTI",
            side=Side.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
            estimated_price_usd=100.0,
            estimated_value_usd=1000.0,
            rationale="Rebalance",
            status=ActionStatus.DRAFTED,
            created_at=datetime.now(timezone.utc),
            proposed_by_skill_version=SkillVersionRef(skill_name="private-action-drafting", skill_version="0.1.0"),
            ips_version_referenced=RelatedIPSVersion(ips_id="ips1", version=1),
        )
        mock_mcp.get_document.return_value = client._dict_factory(action)
        act = client.get_proposed_action("act_1")
        assert act is not None
        assert act.action_id == "act_1"

        client.set_proposed_action(action)
        mock_mcp.set_document.assert_called_with("proposed_actions", "act_1", client._dict_factory(action))

        client.update_proposed_action_status("act_1", ActionStatus.APPROVED, {"review_passed": True})
        mock_mcp.update_document.assert_called_with(
            "proposed_actions", "act_1", {"status": "approved", "review_passed": True}
        )

        # Audit Log
        from src.orchestrator.contracts.audit_log import Actor, ActorType, AuditLogEntry, EventType

        entry = AuditLogEntry(
            log_id="log_1",
            timestamp=datetime.now(timezone.utc),
            event_type=EventType.ACTION_PROPOSED,
            actor=Actor(type=ActorType.AGENT, skill_name="private-action-drafting"),
            user_id="u1",
            payload={"test": "val"},
        )
        client.append_audit_log(entry)
        mock_mcp.set_document.assert_called_with("audit_log", "log_1", client._dict_factory(entry))

        # IPS
        ips_data = {
            "ips_id": "ips_1",
            "user_id": "u1",
            "version": 1,
            "status": "active",
            "effective_date": "2026-01-01",
            "risk_tolerance": "moderate",
            "time_horizon_years": 10,
            "target_allocation": [
                {"asset_class": "equity", "target_percent": 60, "min_percent": 50, "max_percent": 70}
            ],
            "constraints": {"concentration_limit_percent": 15},
            "created_at": "2026-01-01T00:00:00Z",
        }
        mock_mcp.list_documents.return_value = [ips_data]
        ips = client.get_active_ips("ips_1")
        assert ips is not None
        assert ips.ips_id == "ips_1"

        ips_by_user = client.get_active_ips_by_user("u1")
        assert ips_by_user is not None
        assert ips_by_user.user_id == "u1"

        # Reports & Profiles
        mock_mcp.get_document.return_value = {"total_income_usd": 1000}
        client.set_spending_report("u1", {"total_income_usd": 1000})
        mock_mcp.set_document.assert_called_with("spending_reports", "u1", {"total_income_usd": 1000})
        assert client.get_spending_report("u1") == {"total_income_usd": 1000}

        mock_mcp.get_document.return_value = {"drift_detected": False}
        client.set_drift_report("u1", {"drift_detected": False})
        mock_mcp.set_document.assert_called_with("drift_reports", "u1", {"drift_detected": False})
        assert client.get_drift_report("u1") == {"drift_detected": False}

        mock_mcp.get_document.return_value = {"name": "Test User"}
        client.set_user_profile("u1", {"name": "Test User"})
        mock_mcp.set_document.assert_called_with("user_profiles", "u1", {"name": "Test User"})
        assert client.get_user_profile("u1") == {"name": "Test User"}


def test_firestore_client_mcp_fallback_on_exception():
    """Error/resilience path: FirestoreClient catches MCP errors and falls back to direct SDK."""
    mock_mcp = MagicMock()
    mock_mcp.get_document.side_effect = RuntimeError("MCP connection timed out")
    mock_mcp.set_document.side_effect = RuntimeError("MCP connection timed out")
    mock_mcp.update_document.side_effect = RuntimeError("MCP connection timed out")
    mock_mcp.list_documents.side_effect = RuntimeError("MCP connection timed out")

    with patch("google.cloud.firestore.Client"):
        client = FirestoreClient(project="test-project", use_mcp=True)
        client.mcp_client = mock_mcp

        # Direct SDK mock
        client._get_holdings_direct = MagicMock(return_value=None)
        client._set_holdings_direct = MagicMock()
        client._get_liabilities_direct = MagicMock(return_value=None)
        client._set_liabilities_direct = MagicMock()
        client._get_proposed_action_direct = MagicMock(return_value=None)
        client._set_proposed_action_direct = MagicMock()
        client._update_proposed_action_status_direct = MagicMock()
        client._append_audit_log_direct = MagicMock()
        client._get_active_ips_direct = MagicMock(return_value=None)
        client._get_active_ips_by_user_direct = MagicMock(return_value=None)
        client._set_spending_report_direct = MagicMock()
        client._get_spending_report_direct = MagicMock(return_value=None)
        client._set_drift_report_direct = MagicMock()
        client._get_drift_report_direct = MagicMock(return_value=None)
        client._set_user_profile_direct = MagicMock()
        client._get_user_profile_direct = MagicMock(return_value=None)

        # Exercise all methods to verify fallback is invoked
        client.get_holdings("u1")
        client._get_holdings_direct.assert_called_once_with("u1")

        mock_h = MagicMock()
        client.set_holdings("u1", mock_h)
        client._set_holdings_direct.assert_called_once_with("u1", mock_h)

        client.get_liabilities("u1")
        client._get_liabilities_direct.assert_called_once_with("u1")

        mock_l = MagicMock()
        client.set_liabilities("u1", mock_l)
        client._set_liabilities_direct.assert_called_once_with("u1", mock_l)

        client.get_proposed_action("act1")
        client._get_proposed_action_direct.assert_called_once_with("act1")

        mock_act = MagicMock()
        mock_act.action_id = "act1"
        client.set_proposed_action(mock_act)
        client._set_proposed_action_direct.assert_called_once_with(mock_act)

        from src.orchestrator.contracts import ActionStatus

        client.update_proposed_action_status("act1", ActionStatus.APPROVED)
        client._update_proposed_action_status_direct.assert_called_once_with("act1", ActionStatus.APPROVED, None)

        mock_entry = MagicMock()
        mock_entry.log_id = "log1"
        client.append_audit_log(mock_entry)
        client._append_audit_log_direct.assert_called_once_with(mock_entry)

        client.get_active_ips("ips1")
        client._get_active_ips_direct.assert_called_once_with("ips1")

        client.get_active_ips_by_user("u1")
        client._get_active_ips_by_user_direct.assert_called_once_with("u1")

        client.set_spending_report("u1", {})
        client._set_spending_report_direct.assert_called_once_with("u1", {})

        client.get_spending_report("u1")
        client._get_spending_report_direct.assert_called_once_with("u1")

        client.set_drift_report("u1", {})
        client._set_drift_report_direct.assert_called_once_with("u1", {})

        client.get_drift_report("u1")
        client._get_drift_report_direct.assert_called_once_with("u1")

        client.set_user_profile("u1", {})
        client._set_user_profile_direct.assert_called_once_with("u1", {})

        client.get_user_profile("u1")
        client._get_user_profile_direct.assert_called_once_with("u1")


def test_firestore_client_mcp_ips_invariant_violation():
    """Invariant check: get_active_ips_by_user raises ValueError if MCP returns multiple active IPS documents."""
    mock_mcp = MagicMock()
    mock_mcp.list_documents.return_value = [
        {"ips_id": "ips1", "user_id": "u1", "status": "active"},
        {"ips_id": "ips2", "user_id": "u1", "status": "active"},
    ]

    with patch("google.cloud.firestore.Client"):
        client = FirestoreClient(project="test-project", use_mcp=True)
        client.mcp_client = mock_mcp
        with pytest.raises(ValueError, match="invariant violated"):
            client.get_active_ips_by_user("u1")
