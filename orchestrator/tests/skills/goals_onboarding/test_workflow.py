from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from orchestrator.contracts.audit_log import EventType
from orchestrator.contracts.goals_onboarding import GoalsOnboardingResult
from orchestrator.contracts.ips import (
    Constraints,
    Goal,
    InvestmentPolicyStatement,
    IPSStatus,
    RiskTolerance,
    TargetAllocation,
)
from orchestrator.contracts.liabilities import Liability, LiabilityType
from orchestrator.skills._skill_metadata import read_skill_version
from orchestrator.state.writers import write_ips_from_interview_result


@pytest.fixture
def sample_interview_result():
    return GoalsOnboardingResult(
        user_id="user_123",
        primary_goal=Goal(name="Retirement", target_amount_usd=1000000.0, target_date="2045-01-01"),
        additional_goals=[Goal(name="Emergency", target_amount_usd=50000.0, target_date="2025-01-01")],
        risk_tolerance=RiskTolerance.MODERATE,
        time_horizon_years=10,
        target_allocation=[
            TargetAllocation(asset_class="equity", target_percent=60, min_percent=50, max_percent=70),
            TargetAllocation(asset_class="bonds", target_percent=30, min_percent=20, max_percent=40),
            TargetAllocation(asset_class="cash", target_percent=10, min_percent=5, max_percent=15),
        ],
        identified_liabilities=[
            Liability(
                liability_id="liab_1",
                type=LiabilityType.MORTGAGE,
                balance_usd=300000.0,
                minimum_payment_usd=2000.0,
            )
        ],
        interview_summary="User seeks balanced growth for retirement and emergency cushion.",
    )


def test_write_ips_initial_trigger_creates_v1(sample_interview_result):
    mock_client = MagicMock()
    mock_client.get_active_ips_by_user.return_value = None

    ips, liab = write_ips_from_interview_result(
        user_id="user_123",
        result=sample_interview_result,
        trigger="initial",
        db_client=mock_client,
    )

    assert ips.version == 1
    assert ips.status == IPSStatus.ACTIVE
    assert ips.user_id == "user_123"
    assert ips.risk_tolerance == RiskTolerance.MODERATE
    assert len(ips.goals) == 2
    assert len(liab.liabilities) == 1

    mock_client.update_ips.assert_called_once_with(ips)
    mock_client.set_liabilities.assert_called_once_with("user_123", liab)
    mock_client.append_audit_log.assert_called_once()

    audit_entry = mock_client.append_audit_log.call_args[0][0]
    assert audit_entry.event_type == EventType.IPS_CREATED
    assert audit_entry.actor.skill_version == read_skill_version("goals-onboarding")
    assert audit_entry.actor.approval_scope == "read:holdings,read:liabilities,read:spending,read:ips"


def test_write_ips_carries_registry_entry_id_and_approval_scope(sample_interview_result):
    mock_client = MagicMock()
    mock_client.get_active_ips_by_user.return_value = None

    _, _ = write_ips_from_interview_result(
        user_id="user_123",
        result=sample_interview_result,
        trigger="initial",
        registry_entry_id="projects/test/revisions/rev-goals-1",
        db_client=mock_client,
    )

    audit_entry = mock_client.append_audit_log.call_args[0][0]
    assert audit_entry.actor.registry_entry_id == "projects/test/revisions/rev-goals-1"
    assert audit_entry.actor.approval_scope == "read:holdings,read:liabilities,read:spending,read:ips"


def test_write_ips_dynamic_skill_version_from_frontmatter(sample_interview_result, monkeypatch):
    mock_client = MagicMock()
    mock_client.get_active_ips_by_user.return_value = None

    monkeypatch.setattr(
        "orchestrator.state.writers.read_skill_version",
        lambda skill_name: "9.9.9",
    )

    _, _ = write_ips_from_interview_result(
        user_id="user_123",
        result=sample_interview_result,
        trigger="initial",
        db_client=mock_client,
    )

    audit_entry = mock_client.append_audit_log.call_args[0][0]
    assert audit_entry.actor.skill_version == "9.9.9"


def test_write_ips_revision_trigger_supersedes_existing(sample_interview_result):
    mock_client = MagicMock()
    existing_ips = InvestmentPolicyStatement(
        ips_id="existing_ips_999",
        user_id="user_123",
        version=2,
        status=IPSStatus.ACTIVE,
        effective_date="2023-01-01",
        risk_tolerance=RiskTolerance.CONSERVATIVE,
        time_horizon_years=5,
        target_allocation=[],
        constraints=Constraints(concentration_limit_percent=15.0),
        created_at=datetime.now(timezone.utc),
    )
    mock_client.get_active_ips.return_value = existing_ips

    ips, liab = write_ips_from_interview_result(
        user_id="user_123",
        result=sample_interview_result,
        trigger="life_event",
        existing_ips_ref="existing_ips_999",
        db_client=mock_client,
    )

    assert ips.ips_id == "existing_ips_999"
    assert ips.version == 3
    assert ips.risk_tolerance == RiskTolerance.MODERATE

    mock_client.update_ips.assert_called_once_with(ips)
    audit_entry = mock_client.append_audit_log.call_args[0][0]
    assert audit_entry.event_type == EventType.IPS_SUPERSEDED
    assert audit_entry.actor.skill_version == read_skill_version("goals-onboarding")


def test_write_ips_audit_log_failure_fails_closed(sample_interview_result):
    mock_client = MagicMock()
    mock_client.append_audit_log.side_effect = Exception("Firestore connection failure")

    with pytest.raises(RuntimeError, match="Audit log write failed for IPS creation"):
        write_ips_from_interview_result(
            user_id="user_123",
            result=sample_interview_result,
            trigger="initial",
            db_client=mock_client,
        )
