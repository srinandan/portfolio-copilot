from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.workflow import Workflow
from google.genai.types import Part, UserContent

from orchestrator.contracts.audit_log import AuditLogEntry, EventType
from orchestrator.contracts.drift_report import DriftReport
from orchestrator.contracts.goals_onboarding import Goal, GoalsOnboardingResult
from orchestrator.contracts.ips import RelatedIPSVersion, RiskTolerance
from orchestrator.contracts.proposed_action import (
    ActionStatus,
    ActionType,
    OrderType,
    ProposedAction,
    Side,
    SkillVersionRef,
)
from orchestrator.contracts.reviewer_verdict import ReviewerVerdict, RuleResult
from orchestrator.planner import root_planner
from orchestrator.registry_client import Skill


class FakeFirestore:
    def __init__(self):
        from datetime import date

        from orchestrator.contracts.holdings import HoldingsSnapshot
        from orchestrator.contracts.ips import Constraints, InvestmentPolicyStatement, IPSStatus

        self.audit_entries: List[AuditLogEntry] = []
        self.proposed_actions: Dict[str, ProposedAction] = {}
        self.ips = InvestmentPolicyStatement(
            ips_id="ips_e2e_1",
            user_id="u_pipe",
            version=1,
            status=IPSStatus.ACTIVE,
            effective_date=date(2026, 1, 1),
            risk_tolerance=RiskTolerance.MODERATE,
            time_horizon_years=10,
            target_allocation=[],
            constraints=Constraints(
                excluded_tickers=[],
                excluded_sectors=[],
                concentration_limit_percent=25.0,
            ),
            created_at=datetime.now(timezone.utc),
        )
        self.holdings = HoldingsSnapshot(
            user_id="u_pipe",
            as_of=datetime.now(timezone.utc),
            positions=[],
            cash_usd=100000.0,
            total_value_usd=100000.0,
        )

    def append_audit_log(self, entry: AuditLogEntry) -> None:
        self.audit_entries.append(entry)

    def set_proposed_action(self, action: ProposedAction) -> None:
        self.proposed_actions[action.action_id] = action

    def update_proposed_action_status(
        self,
        action_id: str,
        status: ActionStatus,
        updated_fields: Optional[Dict[str, Any]] = None,
    ) -> None:
        if action_id in self.proposed_actions:
            self.proposed_actions[action_id].status = status
            if updated_fields:
                for k, v in updated_fields.items():
                    setattr(self.proposed_actions[action_id], k, v)

    def get_active_ips_by_user(self, user_id: str) -> Any:
        return self.ips

    def get_holdings(self, user_id: str) -> Any:
        return self.holdings


@pytest.fixture
def mock_pipeline_environment():
    fake_fs = FakeFirestore()

    def fake_dispatch(skill_name: str, **kwargs) -> Any:
        if skill_name == "private-goals-onboarding":
            return GoalsOnboardingResult(
                user_id="u_pipe",
                primary_goal=Goal(
                    name="Retirement",
                    target_amount_usd=1000000.0,
                    target_date="2045-01-01",
                ),
                risk_tolerance=RiskTolerance.MODERATE,
                time_horizon_years=10,
                target_allocation=[],
                interview_summary="Goals onboarding complete",
            )
        if skill_name == "private-portfolio-analysis":
            return DriftReport(
                entries=[],
                unclassified_value_usd=0.0,
                rebalance_recommended=True,
            )
        if skill_name == "private-action-drafting":
            return ProposedAction(
                action_id="act_e2e_1",
                session_id="sess_pipe_1",
                type=ActionType.TRADE,
                ticker="VTI",
                side=Side.BUY,
                quantity=10.0,
                order_type=OrderType.MARKET,
                estimated_price_usd=250.0,
                estimated_value_usd=2500.0,
                rationale="Rebalancing into equity",
                ips_version_referenced=RelatedIPSVersion(ips_id="ips_e2e_1", version=1),
                proposed_by_skill_version=SkillVersionRef(
                    skill_name="private-action-drafting",
                    skill_version="0.1.0",
                ),
                status=ActionStatus.DRAFTED,
                created_at=datetime.now(timezone.utc),
            )
        if skill_name == "private-reviewer":
            return ReviewerVerdict(
                verdict_id="verdict_e2e_1",
                action_id="act_e2e_1",
                ips_version_checked_against=RelatedIPSVersion(ips_id="ips_e2e_1", version=1),
                rule_results=[
                    RuleResult(rule_id="r1", description="rule 1", passed=True)
                ],
                overall_pass=True,
                requires_human_approval=True,
                reviewer_skill_version=SkillVersionRef(
                    skill_name="private-reviewer",
                    skill_version="0.1.0",
                ),
                reviewed_at=datetime.now(timezone.utc),
            )
        return None

    with (
        patch(
            "orchestrator.planner.AgentRegistryClient.list_authorized_skills",
            new_callable=AsyncMock,
        ) as mock_list_skills,
        patch(
            "orchestrator.planner.dispatch_managed_skill",
            side_effect=fake_dispatch,
        ),
        patch("orchestrator.planner.FirestoreClient", return_value=fake_fs),
        patch("orchestrator.state.preloader.FirestoreClient", return_value=fake_fs),
        patch("orchestrator.state.writers.FirestoreClient", return_value=fake_fs),
        patch("orchestrator.gates.hitl.FirestoreClient", return_value=fake_fs),
        patch("orchestrator.gates.execution.FirestoreClient", return_value=fake_fs),
        patch("orchestrator.planner.write_ips_from_interview_result", return_value=(fake_fs.ips, MagicMock())),
        patch("orchestrator.gates.execution.AlpacaExecutor") as mock_alpaca_cls,
    ):
        mock_list_skills.return_value = [
            Skill(
                name="projects/p/locations/l/skills/private-goals-onboarding",
                target_state="TARGET_STATE_ACTIVE",
                default_revision="rev1",
            ),
            Skill(
                name="projects/p/locations/l/skills/private-portfolio-analysis",
                target_state="TARGET_STATE_ACTIVE",
                default_revision="rev1",
            ),
            Skill(
                name="projects/p/locations/l/skills/private-action-drafting",
                target_state="TARGET_STATE_ACTIVE",
                default_revision="rev1",
            ),
            Skill(
                name="projects/p/locations/l/skills/private-reviewer",
                target_state="TARGET_STATE_ACTIVE",
                default_revision="rev1",
            ),
        ]
        mock_alpaca = mock_alpaca_cls.return_value
        mock_alpaca.submit_order.return_value = MagicMock(broker_order_id="broker_order_id_e2e_999")

        yield fake_fs, mock_alpaca


@pytest.mark.asyncio
async def test_full_pipeline_approval_to_execution(mock_pipeline_environment):
    """Verifies the complete end-to-end orchestration pipeline from goals onboarding -> HITL approve -> Alpaca trade."""
    fake_fs, mock_alpaca = mock_pipeline_environment

    agent = Workflow(
        name="root_pipeline_e2e",
        edges=[("START", root_planner)],
    )
    session_service = InMemorySessionService()
    runner = Runner(
        app_name="portfolio_copilot_e2e",
        agent=agent,
        session_service=session_service,
        auto_create_session=True,
    )

    # Cycle 1: Initiate pipeline with goal trigger
    response_stream = runner.run_async(
        user_id="u_pipe",
        session_id="sess_pipe_1",
        new_message=UserContent(parts=[Part.from_text(text='{"user_id": "u_pipe", "trigger": "initial"}')]),
    )
    events = [e async for e in response_stream]
    assert len(events) > 0

    # Verify initial audit trail and DRAFTED state
    event_types = [e.event_type for e in fake_fs.audit_entries]
    assert EventType.SKILL_INVOKED in event_types
    assert EventType.ACTION_PROPOSED in event_types
    assert EventType.REVIEW_COMPLETED in event_types
    assert EventType.APPROVAL_REQUESTED in event_types

    assert "act_e2e_1" in fake_fs.proposed_actions
    assert fake_fs.proposed_actions["act_e2e_1"].status == ActionStatus.DRAFTED

    # Cycle 2: Resume pipeline with human approval
    resume_stream = runner.run_async(
        user_id="u_pipe",
        session_id="sess_pipe_1",
        new_message=UserContent(parts=[Part.from_text(text='{"decision": "approve", "user_id": "u_pipe"}')]),
    )
    resume_events = [e async for e in resume_stream]
    assert len(resume_events) > 0

    # Verify execution gate ran, Alpaca was called, and status transitioned to EXECUTED
    mock_alpaca.submit_order.assert_called_once()
    assert fake_fs.proposed_actions["act_e2e_1"].status == ActionStatus.EXECUTED

    final_event_types = [e.event_type for e in fake_fs.audit_entries]
    assert EventType.APPROVAL_GRANTED in final_event_types
    assert EventType.ACTION_EXECUTED in final_event_types


@pytest.mark.asyncio
async def test_full_pipeline_rejection_skips_execution(mock_pipeline_environment):
    """Verifies that when HITL rejects a ProposedAction, the execution gate is skipped and Alpaca is never called."""
    fake_fs, mock_alpaca = mock_pipeline_environment

    agent = Workflow(
        name="root_pipeline_e2e_rejection",
        edges=[("START", root_planner)],
    )
    session_service = InMemorySessionService()
    runner = Runner(
        app_name="portfolio_copilot_e2e",
        agent=agent,
        session_service=session_service,
        auto_create_session=True,
    )

    # Cycle 1: Initiate pipeline
    response_stream = runner.run_async(
        user_id="u_pipe",
        session_id="sess_pipe_2",
        new_message=UserContent(parts=[Part.from_text(text='{"user_id": "u_pipe", "trigger": "initial"}')]),
    )
    _ = [e async for e in response_stream]

    # Cycle 2: Resume pipeline with human rejection
    resume_stream = runner.run_async(
        user_id="u_pipe",
        session_id="sess_pipe_2",
        new_message=UserContent(
            parts=[Part.from_text(text='{"decision": "reject", "reason": "Not right now", "user_id": "u_pipe"}')]
        ),
    )
    _ = [e async for e in resume_stream]

    # Verify Alpaca was NOT called and status transitioned to REJECTED
    mock_alpaca.submit_order.assert_not_called()
    assert fake_fs.proposed_actions["act_e2e_1"].status == ActionStatus.REJECTED

    final_event_types = [e.event_type for e in fake_fs.audit_entries]
    assert EventType.APPROVAL_REJECTED in final_event_types
    assert EventType.ACTION_EXECUTED not in final_event_types
