from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.adk import Context
from google.adk.events import RequestInput
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.workflow import Workflow, node
from google.genai.types import Part, UserContent

from src.orchestrator.contracts import Goal, GoalsOnboardingResult, RiskTolerance
from src.orchestrator.planner import root_planner
from src.orchestrator.registry_client import Skill

execution_count = 0


@node(name="counter_node", rerun_on_resume=False)
async def counter_node(ctx: Context, node_input: str):
    global execution_count
    execution_count += 1
    return f"Count: {execution_count}"


@node(name="pausing_node", rerun_on_resume=False)
async def pausing_node(ctx: Context, node_input: str):
    # Wait for the input from the resume, which acts like a yield
    result = yield RequestInput(message="Pause here")
    yield result


@node(rerun_on_resume=True)
async def checkpoint_workflow(ctx: Context, node_input: Any):
    count_result = await ctx.run_node(counter_node, node_input="test")
    approval = await ctx.run_node(pausing_node, node_input="test")
    return {"count": count_result, "approval": approval}


@pytest.mark.asyncio
async def test_checkpointing():
    """Verify that ADK's automatic checkpointing skips re-executing already-completed sub-nodes when resuming."""
    global execution_count
    execution_count = 0

    agent = Workflow(
        name="test_workflow",
        edges=[("START", checkpoint_workflow)],
    )

    session_service = InMemorySessionService()
    memory_service = InMemoryMemoryService()
    runner = Runner(
        app_name="test_app",
        agent=agent,
        session_service=session_service,
        memory_service=memory_service,
        auto_create_session=True,
    )

    session_id = "test_session_123"

    # --- FIRST RUN ---
    response_stream = runner.run_async(
        user_id="user_123", session_id=session_id, new_message=UserContent(parts=[Part.from_text(text="start_goal")])
    )

    events = []
    async for event in response_stream:
        events.append(event)

    last_event = events[-1]

    # Verify the counter node executed exactly once
    assert execution_count == 1

    # Check that a request input (pause) was returned
    function_calls = last_event.content.parts if last_event.content and last_event.content.parts else []
    interrupt_id = None
    for part in function_calls:
        if part.function_call and part.function_call.name == "adk_request_input":
            interrupt_id = part.function_call.id
            break

    assert interrupt_id is not None, "Did not find request_input interrupt"

    # --- SECOND RUN (RESUME) ---
    response_part = Part.from_function_response(
        name="adk_request_input",
        response={"interruptId": interrupt_id, "payload": "approved"},
    )
    response_part.function_response.id = interrupt_id

    response_stream = runner.run_async(
        user_id="user_123",
        session_id=session_id,
        invocation_id=last_event.invocation_id,
        new_message=UserContent(parts=[response_part]),
    )

    events2 = []
    async for event in response_stream:
        events2.append(event)

    assert len(events2) > 0, "resume produced no events"
    assert events2[-1].output == {
        "count": "Count: 1",
        "approval": {"interruptId": interrupt_id, "payload": "approved"},
    }

    # Crucially, execution_count MUST still be 1 (checkpointing bypassed running counter_node)
    assert execution_count == 1


@pytest.mark.asyncio
async def test_root_planner_trace():
    """Verify the root planner dynamic workflow executes correctly and queries the mocked registry."""
    agent = Workflow(
        name="test_root",
        edges=[("START", root_planner)],
    )
    session_service = InMemorySessionService()
    memory_service = InMemoryMemoryService()
    runner = Runner(
        app_name="test_app",
        agent=agent,
        session_service=session_service,
        memory_service=memory_service,
        auto_create_session=True,
    )

    with patch(
        "src.orchestrator.planner.AgentRegistryClient.list_authorized_skills", new_callable=AsyncMock
    ) as mock_list:
        mock_list.return_value = [
            Skill(
                name="projects/test-project/locations/test-location/skills/dummy_skill_1",
                target_state="TARGET_STATE_ACTIVE",
                default_revision="rev1",
            ),
            Skill(
                name="projects/test-project/locations/test-location/skills/dummy_skill_2",
                target_state="TARGET_STATE_ACTIVE",
                default_revision="rev2",
            ),
        ]

        response_stream = runner.run_async(
            user_id="user_123",
            session_id="session_456",
            new_message=UserContent(parts=[Part.from_text(text="test_goal")]),
        )

        events = []
        async for event in response_stream:
            events.append(event)

        last_event = events[-1]
        assert last_event.output == [
            "projects/test-project/locations/test-location/skills/dummy_skill_1_completed",
            "projects/test-project/locations/test-location/skills/dummy_skill_2_completed",
        ]


@pytest.mark.asyncio
async def test_root_planner_json_input():
    agent = Workflow(
        name="test_root",
        edges=[("START", root_planner)],
    )
    session_service = InMemorySessionService()
    memory_service = InMemoryMemoryService()
    runner = Runner(
        app_name="test_app",
        agent=agent,
        session_service=session_service,
        memory_service=memory_service,
        auto_create_session=True,
    )

    with (
        patch(
            "src.orchestrator.planner.AgentRegistryClient.list_authorized_skills", new_callable=AsyncMock
        ) as mock_list,
        patch("src.orchestrator.planner.emit_skill_invoked_audit"),
        patch("src.orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock) as mock_dispatch,
        patch("src.orchestrator.planner.write_ips_from_interview_result") as mock_write,
    ):
        mock_write.return_value = (
            MagicMock(ips_id="ips-123", version=1, risk_tolerance=RiskTolerance.MODERATE, time_horizon_years=10),
            MagicMock(),
        )
        mock_dispatch.return_value = GoalsOnboardingResult(
            user_id="u4",
            primary_goal=Goal(name="Retirement", target_amount_usd=1000000.0, target_date="2045-01-01"),
            risk_tolerance=RiskTolerance.MODERATE,
            time_horizon_years=10,
            target_allocation=[],
            interview_summary="Goals onboarding complete",
        )

        mock_list.return_value = [
            Skill(
                name="projects/test-project/locations/test-location/skills/private-goals-onboarding",
                target_state="TARGET_STATE_ACTIVE",
                default_revision="rev1",
            ),
        ]

        response_stream = runner.run_async(
            user_id="user_123",
            session_id="session_456",
            new_message=UserContent(parts=[Part.from_text(text='{"user_id": "u4", "trigger": "initial"}')]),
        )

        events = []
        async for event in response_stream:
            events.append(event)

        assert len(events) > 0
        assert mock_dispatch.call_args[0][0] == "private-goals-onboarding"
        assert mock_dispatch.call_args[1]["node_input"] == {"user_id": "u4", "trigger": "initial"}


@pytest.mark.asyncio
async def test_root_planner_dispatches_goals_onboarding_with_realistic_name():
    """Verify planner extracts short name from full resource path and invokes managed dispatcher."""
    agent = Workflow(
        name="test_root",
        edges=[("START", root_planner)],
    )
    session_service = InMemorySessionService()
    memory_service = InMemoryMemoryService()
    runner = Runner(
        app_name="test_app",
        agent=agent,
        session_service=session_service,
        memory_service=memory_service,
        auto_create_session=True,
    )

    with (
        patch(
            "src.orchestrator.planner.AgentRegistryClient.list_authorized_skills", new_callable=AsyncMock
        ) as mock_list,
        patch("src.orchestrator.planner.emit_skill_invoked_audit"),
        patch("src.orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock) as mock_dispatch,
        patch("src.orchestrator.planner.write_ips_from_interview_result") as mock_write,
    ):
        mock_write.return_value = (
            MagicMock(ips_id="ips-123", version=1, risk_tolerance=RiskTolerance.MODERATE, time_horizon_years=10),
            MagicMock(),
        )
        mock_dispatch.return_value = GoalsOnboardingResult(
            user_id="u4",
            primary_goal=Goal(name="Retirement", target_amount_usd=1000000.0, target_date="2045-01-01"),
            risk_tolerance=RiskTolerance.MODERATE,
            time_horizon_years=10,
            target_allocation=[],
            interview_summary="Goals onboarding complete",
        )

        mock_list.return_value = [
            Skill(
                name="projects/test-proj-123/locations/us-central1/skills/private-goals-onboarding",
                target_state="TARGET_STATE_ACTIVE",
                default_revision="rev-v1",
            ),
        ]

        response_stream = runner.run_async(
            user_id="user_123",
            session_id="session_456",
            new_message=UserContent(parts=[Part.from_text(text='{"user_id": "u4", "trigger": "initial"}')]),
        )

        events = []
        async for event in response_stream:
            events.append(event)

        assert len(events) > 0
        mock_dispatch.assert_awaited_once()


@pytest.mark.asyncio
async def test_root_planner_invalid_json():
    from google.adk.runners import Runner
    from google.adk.workflow import Workflow

    agent = Workflow(
        name="test_root",
        edges=[("START", root_planner)],
    )

    session_service = InMemorySessionService()
    runner = Runner(app_name="test_app", agent=agent, session_service=session_service, auto_create_session=True)

    with (
        patch(
            "src.orchestrator.planner.AgentRegistryClient.list_authorized_skills", new_callable=AsyncMock
        ) as mock_list,
        patch("src.orchestrator.planner.emit_skill_invoked_audit"),
        patch("src.orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock) as mock_dispatch,
    ):
        mock_dispatch.return_value = {"status": "completed"}
        mock_list.return_value = [
            Skill(
                name="projects/test-project/locations/test-location/skills/private-goals-onboarding",
                target_state="TARGET_STATE_ACTIVE",
                default_revision="rev1",
            ),
        ]
        response_stream = runner.run_async(
            user_id="user_123", session_id="s1", new_message=UserContent(parts=[Part.from_text(text="invalid json {")])
        )
        events = [e async for e in response_stream]
        assert len(events) > 0
        assert len(events) > 0


@pytest.mark.asyncio
async def test_root_planner_end_to_end_pa_then_ad():
    """Verify registry returns both PA and AD; assert AD receives PA's drift_report via context chaining."""
    agent = Workflow(
        name="test_root",
        edges=[("START", root_planner)],
    )
    session_service = InMemorySessionService()
    memory_service = InMemoryMemoryService()
    runner = Runner(
        app_name="test_app",
        agent=agent,
        session_service=session_service,
        memory_service=memory_service,
        auto_create_session=True,
    )

    with (
        patch("src.orchestrator.planner.AgentRegistryClient.list_authorized_skills", new_callable=AsyncMock) as mock_list,
        patch("src.orchestrator.planner.emit_skill_invoked_audit"),
        patch("src.orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock) as mock_dispatch,
        patch("src.orchestrator.state.preloader.FirestoreClient") as mock_fs_cls,
    ):
        mock_list.return_value = [
            Skill(name="projects/p/locations/l/skills/private-portfolio-analysis", target_state="TARGET_STATE_ACTIVE", default_revision="v1"),
            Skill(name="projects/p/locations/l/skills/private-action-drafting", target_state="TARGET_STATE_ACTIVE", default_revision="v1"),
        ]

        mock_fs = mock_fs_cls.return_value
        fake_ips = MagicMock(ips_id="ips_1", version=1)
        fake_ips.model_dump.return_value = {"ips_id": "ips_1", "version": 1}
        fake_holdings = MagicMock(total_value_usd=100000.0, positions=[], cash_usd=100000.0)
        fake_holdings.model_dump.return_value = {"total_value_usd": 100000.0, "positions":[], "cash_usd": 100000.0}

        mock_fs.get_active_ips_by_user.return_value = fake_ips
        mock_fs.get_holdings.return_value = fake_holdings

        async def fake_dispatch(skill_name, **kwargs):
            if skill_name == "private-portfolio-analysis":
                return {"entries": [], "unclassified_value_usd": 0.0, "rebalance_recommended": False}
            if skill_name == "private-action-drafting":
                return {}
            return {}

        mock_dispatch.side_effect = fake_dispatch

        response_stream = runner.run_async(
            user_id="user_chain",
            session_id="session_chain_1",
            new_message=UserContent(parts=[Part.from_text(text='{"user_id": "user_chain"}')]),
        )

        events = [e async for e in response_stream]
        assert len(events) > 0
        last_event = events[-1]
        assert any("portfolio-analysis_result" in str(out) for out in last_event.output)
        assert any("action-drafting_result" in str(out) for out in last_event.output)

        # Ensure AD call received PA's drift_report in node_input
        ad_call = [c for c in mock_dispatch.call_args_list if c[0][0] == "private-action-drafting"][0]
        assert "drift_report" in ad_call[1]["node_input"]
        assert ad_call[1]["node_input"]["drift_report"] == {"entries": [], "unclassified_value_usd": 0.0, "rebalance_recommended": False}


@pytest.mark.asyncio
async def test_root_planner_skips_research_without_question():
    """Verify research is skipped cleanly when no research_question was requested."""
    agent = Workflow(
        name="test_root",
        edges=[("START", root_planner)],
    )
    session_service = InMemorySessionService()
    memory_service = InMemoryMemoryService()
    runner = Runner(
        app_name="test_app",
        agent=agent,
        session_service=session_service,
        memory_service=memory_service,
        auto_create_session=True,
    )

    with (
        patch("src.orchestrator.planner.AgentRegistryClient.list_authorized_skills", new_callable=AsyncMock) as mock_list,
        patch("src.orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock) as mock_dispatch,
    ):
        mock_list.return_value = [
            Skill(
                name="projects/test-proj/locations/us-central1/skills/private-research",
                target_state="TARGET_STATE_ACTIVE",
                default_revision="rev-research-1",
            ),
        ]

        response_stream = runner.run_async(
            user_id="user_123",
            session_id="session_456",
            new_message=UserContent(parts=[Part.from_text(text='{"user_id": "u5"}')]),
        )

        events = [e async for e in response_stream]
        last_event = events[-1]

        mock_dispatch.assert_not_called()
        assert not any("research_result:" in str(item) for item in last_event.output)


@pytest.mark.asyncio
async def test_root_planner_pipeline_order_stable():
    """Verify registry returning skills in reverse order still runs them in PIPELINE_SKILL_ORDER."""
    agent = Workflow(
        name="test_root",
        edges=[("START", root_planner)],
    )
    session_service = InMemorySessionService()
    memory_service = InMemoryMemoryService()
    runner = Runner(
        app_name="test_app",
        agent=agent,
        session_service=session_service,
        memory_service=memory_service,
        auto_create_session=True,
    )

    with (
        patch("src.orchestrator.planner.AgentRegistryClient.list_authorized_skills", new_callable=AsyncMock) as mock_list,
        patch("src.orchestrator.planner.emit_skill_invoked_audit"),
        patch("src.orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock) as mock_dispatch,
        patch("src.orchestrator.state.preloader.FirestoreClient") as mock_fs_cls,
    ):
        # Return in reverse order
        mock_list.return_value = [
            Skill(name="skills/private-action-drafting", target_state="TARGET_STATE_ACTIVE", default_revision="v1"),
            Skill(name="skills/private-research", target_state="TARGET_STATE_ACTIVE", default_revision="v1"),
            Skill(name="skills/private-portfolio-analysis", target_state="TARGET_STATE_ACTIVE", default_revision="v1"),
        ]

        mock_fs = mock_fs_cls.return_value
        fake_ips = MagicMock(ips_id="ips_1", version=1)
        fake_ips.model_dump.return_value = {"ips_id": "ips_1", "version": 1}
        fake_holdings = MagicMock(total_value_usd=100000.0, positions=[], cash_usd=100000.0)
        fake_holdings.model_dump.return_value = {"total_value_usd": 100000.0, "positions":[], "cash_usd": 100000.0}

        mock_fs.get_active_ips_by_user.return_value = fake_ips
        mock_fs.get_holdings.return_value = fake_holdings
        mock_dispatch.return_value = {}

        response_stream = runner.run_async(
            user_id="user_chain",
            session_id="session_chain_1",
            new_message=UserContent(parts=[Part.from_text(text='{"user_id": "user_chain", "research_question": "tech stocks"}')]),
        )

        events = [e async for e in response_stream]
        last_event = events[-1]

        outputs = [str(o) for o in last_event.output]
        pa_idx = next(i for i, out in enumerate(outputs) if "portfolio-analysis_result" in out)
        res_idx = next(i for i, out in enumerate(outputs) if "research_result" in out)
        ad_idx = next(i for i, out in enumerate(outputs) if "action-drafting_result" in out)

        assert pa_idx < res_idx < ad_idx, f"Pipeline order violated: PA={pa_idx}, Res={res_idx}, AD={ad_idx}"



