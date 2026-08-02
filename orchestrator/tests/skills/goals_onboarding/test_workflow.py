from unittest.mock import MagicMock, patch

import pytest
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.workflow import Workflow, node
from google.genai.types import Part, UserContent

from src.orchestrator.skills.goals_onboarding import goals_onboarding_skill


# In ADK, we must return the result of run_node for the suspend/resume to bubble up correctly
@node(name="start_wrapper", rerun_on_resume=True)
async def start_wrapper(ctx, node_input):
    return await ctx.run_node(goals_onboarding_skill, node_input={"user_id": "u1", "trigger": "initial"})

def get_interrupt_id(events):
    if not events: return None
    last_event = events[-1]
    if last_event.content and last_event.content.parts:
        for part in last_event.content.parts:
            if part.function_call and part.function_call.name == "adk_request_input":
                return part.function_call.id
    for e in reversed(events):
        if e.content and e.content.parts:
            for part in e.content.parts:
                if part.function_call and part.function_call.name == "adk_request_input":
                    return part.function_call.id
    return None

@pytest.mark.asyncio
async def test_goals_onboarding_workflow_abandonment():
    """Verify that if the interview is abandoned (not all RequestInputs fulfilled), no writes occur to Firestore."""
    agent = Workflow(
        name="test_onboarding",
        edges=[("START", start_wrapper)],
    )

    session_service = InMemorySessionService()
    memory_service = InMemoryMemoryService()
    runner = Runner(app_name="test_app", agent=agent, session_service=session_service, memory_service=memory_service, auto_create_session=True)

    with patch("src.orchestrator.skills.goals_onboarding.FirestoreClient") as MockFirestoreClient:
        mock_db_client = MagicMock()
        MockFirestoreClient.return_value = mock_db_client

        response_stream = runner.run_async(
            user_id="u1",
            session_id="s1",
            new_message=UserContent(parts=[Part.from_text(text="start")])
        )

        events = [e async for e in response_stream]

        assert mock_db_client.update_ips.call_count == 0
        assert mock_db_client.set_liabilities.call_count == 0
        assert mock_db_client.append_audit_log.call_count == 1
        assert get_interrupt_id(events) is not None


from unittest.mock import AsyncMock

from src.orchestrator.contracts import IPSStatus, RiskTolerance


@pytest.mark.asyncio
async def test_goals_onboarding_skill_direct_call():
    """Verify that when the interview finishes, all Firestore writes occur properly."""
    with patch("src.orchestrator.skills.goals_onboarding.FirestoreClient") as MockFirestoreClient:
        mock_db_client = MagicMock()
        MockFirestoreClient.return_value = mock_db_client
        mock_db_client.get_active_ips.return_value = None # initial state

        # Mock the context
        mock_ctx = MagicMock()
        mock_ctx.run_node = AsyncMock(return_value={
            "goals": [{"name": "Retirement", "target_amount_usd": 1000000, "target_date": "2045-01-01"}],
            "risk_tolerance": RiskTolerance.MODERATE,
            "time_horizon_years": 10,
            "liabilities": [],
            "reserve_months": 6.0,
            "known_upcoming_expenses_usd": 0.0,
            "target_allocation": [{"asset_class": "equity", "target_percent": 60, "min_percent": 50, "max_percent": 70}],
            "constraints": {"concentration_limit_percent": 15},
            "user_id": "u2",
            "trigger": "initial"
        })
        mock_ctx.add_events_to_memory = AsyncMock()

        gen = goals_onboarding_skill.run(ctx=mock_ctx, node_input={"user_id": "u2", "trigger": "initial"})
        result = None
        async for item in gen:
            result = item.output

        # Check writes
        assert mock_db_client.update_ips.call_count == 1
        written_ips = mock_db_client.update_ips.call_args[0][0]
        assert written_ips.user_id == "u2"
        assert written_ips.version == 1
        assert written_ips.status == IPSStatus.ACTIVE

        assert mock_db_client.set_liabilities.call_count == 1
        written_liab = mock_db_client.set_liabilities.call_args[0][1]
        assert written_liab.user_id == "u2"

        assert result["status"] == "completed"
        assert result["version"] == 1


@pytest.mark.asyncio
async def test_goals_onboarding_skill_version_from_frontmatter(monkeypatch):
    """Verify that monkeypatching SKILL_VERSION propagates to both AuditLogEntry writes."""
    import src.orchestrator.skills.goals_onboarding as go_module

    monkeypatch.setattr(go_module, "SKILL_VERSION", "0.9.9-test")

    with patch("src.orchestrator.skills.goals_onboarding.FirestoreClient") as MockFirestoreClient:
        mock_db_client = MagicMock()
        MockFirestoreClient.return_value = mock_db_client
        mock_db_client.get_active_ips.return_value = None

        mock_ctx = MagicMock()
        mock_ctx.run_node = AsyncMock(return_value={
            "goals": [{"name": "Retirement", "target_amount_usd": 1000000, "target_date": "2045-01-01"}],
            "risk_tolerance": RiskTolerance.MODERATE,
            "time_horizon_years": 10,
            "liabilities": [],
            "reserve_months": 6.0,
            "known_upcoming_expenses_usd": 0.0,
            "target_allocation": [{"asset_class": "equity", "target_percent": 60, "min_percent": 50, "max_percent": 70}],
            "constraints": {"concentration_limit_percent": 15},
            "user_id": "u2",
            "trigger": "initial",
        })
        mock_ctx.add_events_to_memory = AsyncMock()

        gen = go_module.goals_onboarding_skill.run(ctx=mock_ctx, node_input={"user_id": "u2", "trigger": "initial"})
        async for _ in gen:
            pass

        assert mock_db_client.append_audit_log.call_count == 2
        first_log = mock_db_client.append_audit_log.call_args_list[0][0][0]
        second_log = mock_db_client.append_audit_log.call_args_list[1][0][0]

        assert first_log.actor.skill_version == "0.9.9-test"
        assert second_log.actor.skill_version == "0.9.9-test"


@pytest.mark.asyncio
async def test_goals_onboarding_partial_interview_failure_emits_audit_and_no_writes():
    """Verify that if the interview fails/drops halfway through, SKILL_INVOCATION_FAILED is emitted and no IPS/liabilities write occurs."""
    with patch("src.orchestrator.skills.goals_onboarding.FirestoreClient") as MockFirestoreClient:
        mock_db_client = MagicMock()
        MockFirestoreClient.return_value = mock_db_client

        mock_ctx = MagicMock()
        mock_ctx.run_node = AsyncMock(side_effect=ValueError("onboarding interview: missing required field(s) in liabilities"))

        with pytest.raises(ValueError, match="missing required field.*liabilities"):
            gen = goals_onboarding_skill.run(ctx=mock_ctx, node_input={"user_id": "u3", "trigger": "initial"})
            async for _ in gen:
                pass

        assert mock_db_client.update_ips.call_count == 0
        assert mock_db_client.set_liabilities.call_count == 0
        assert mock_db_client.append_audit_log.call_count == 2

        invoked_log = mock_db_client.append_audit_log.call_args_list[0][0][0]
        failed_log = mock_db_client.append_audit_log.call_args_list[1][0][0]

        assert invoked_log.event_type.value == "skill_invoked"
        assert failed_log.event_type.value == "skill_invocation_failed"
        assert "liabilities" in (failed_log.detail or "")


