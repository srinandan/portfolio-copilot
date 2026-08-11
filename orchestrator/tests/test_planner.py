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
        # Unrelated skills from registry are ignored and an explicit error is returned
        assert last_event.output == [
            "error: No authorized Portfolio Copilot skills found in Agent Registry to complete the request."
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
        patch(
            "src.orchestrator.planner.AgentRegistryClient.list_authorized_skills", new_callable=AsyncMock
        ) as mock_list,
        patch("src.orchestrator.planner.emit_skill_invoked_audit"),
        patch("src.orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock) as mock_dispatch,
        patch("src.orchestrator.state.preloader.FirestoreClient") as mock_fs_cls,
    ):
        mock_list.return_value = [
            Skill(
                name="projects/p/locations/l/skills/private-portfolio-analysis",
                target_state="TARGET_STATE_ACTIVE",
                default_revision="v1",
            ),
            Skill(
                name="projects/p/locations/l/skills/private-action-drafting",
                target_state="TARGET_STATE_ACTIVE",
                default_revision="v1",
            ),
        ]

        mock_fs = mock_fs_cls.return_value
        fake_ips = MagicMock(ips_id="ips_1", version=1)
        fake_ips.model_dump.return_value = {"ips_id": "ips_1", "version": 1}
        fake_holdings = MagicMock(total_value_usd=100000.0, positions=[], cash_usd=100000.0)
        fake_holdings.model_dump.return_value = {"total_value_usd": 100000.0, "positions": [], "cash_usd": 100000.0}

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
        assert ad_call[1]["node_input"]["drift_report"] == {
            "entries": [],
            "unclassified_value_usd": 0.0,
            "rebalance_recommended": False,
        }


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
        patch(
            "src.orchestrator.planner.AgentRegistryClient.list_authorized_skills", new_callable=AsyncMock
        ) as mock_list,
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
        patch(
            "src.orchestrator.planner.AgentRegistryClient.list_authorized_skills", new_callable=AsyncMock
        ) as mock_list,
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
        fake_holdings.model_dump.return_value = {"total_value_usd": 100000.0, "positions": [], "cash_usd": 100000.0}

        mock_fs.get_active_ips_by_user.return_value = fake_ips
        mock_fs.get_holdings.return_value = fake_holdings
        mock_dispatch.return_value = {}

        response_stream = runner.run_async(
            user_id="user_chain",
            session_id="session_chain_1",
            new_message=UserContent(
                parts=[Part.from_text(text='{"user_id": "user_chain", "research_question": "tech stocks"}')]
            ),
        )

        events = [e async for e in response_stream]
        last_event = events[-1]

        outputs = [str(o) for o in last_event.output]
        pa_idx = next(i for i, out in enumerate(outputs) if "portfolio-analysis_result" in out)
        res_idx = next(i for i, out in enumerate(outputs) if "research_result" in out)
        ad_idx = next(i for i, out in enumerate(outputs) if "action-drafting_result" in out)

        assert pa_idx < res_idx < ad_idx, f"Pipeline order violated: PA={pa_idx}, Res={res_idx}, AD={ad_idx}"


@pytest.mark.asyncio
async def test_root_planner_dispatches_hitl_gate_after_action_drafting():
    """Verify root_planner dispatches hitl_approval_gate when a ProposedAction is drafted."""

    agent = Workflow(
        name="test_root",
        edges=[("START", root_planner)],
    )
    session_service = InMemorySessionService()
    runner = Runner(
        app_name="test_app",
        agent=agent,
        session_service=session_service,
        auto_create_session=True,
    )

    with (
        patch(
            "src.orchestrator.planner.AgentRegistryClient.list_authorized_skills", new_callable=AsyncMock
        ) as mock_list,
        patch("src.orchestrator.planner.emit_skill_invoked_audit"),
        patch("src.orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock) as mock_dispatch,
        patch("src.orchestrator.planner.write_proposed_action"),
        patch("src.orchestrator.state.preloader.FirestoreClient") as mock_fs_cls,
        patch.object(Context, "run_node", new_callable=AsyncMock) as mock_run_node,
    ):
        mock_list.return_value = [
            Skill(name="skills/private-action-drafting", target_state="TARGET_STATE_ACTIVE", default_revision="v1"),
        ]

        mock_fs = mock_fs_cls.return_value
        fake_ips = MagicMock(ips_id="ips_1", version=1)
        fake_ips.model_dump.return_value = {"ips_id": "ips_1", "version": 1}
        fake_holdings = MagicMock(total_value_usd=100000.0, positions=[], cash_usd=100000.0)
        fake_holdings.model_dump.return_value = {"total_value_usd": 100000.0, "positions": [], "cash_usd": 100000.0}
        mock_fs.get_active_ips_by_user.return_value = fake_ips
        mock_fs.get_holdings.return_value = fake_holdings

        from datetime import datetime, timezone

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
        mock_dispatch.return_value = action

        async def fake_run_node(node_func, *args, **kwargs):
            name = getattr(node_func, "name", "")
            if name == "get_skills":
                return ["skills/private-action-drafting"]
            if name == "hitl_approval_gate":
                return {"outcome": "approved", "action_id": "act_1"}
            return None

        mock_run_node.side_effect = fake_run_node

        response_stream = runner.run_async(
            user_id="user_hitl",
            session_id="sess_hitl_1",
            new_message=UserContent(parts=[Part.from_text(text='{"user_id": "user_hitl"}')]),
        )

        events = [e async for e in response_stream]
        last_event = events[-1]

        hitl_calls = [
            c for c in mock_run_node.call_args_list if c[0] and getattr(c[0][0], "name", "") == "hitl_approval_gate"
        ]
        assert len(hitl_calls) == 1, f"Expected 1 hitl_approval_gate call, found {len(hitl_calls)}"
        assert hitl_calls[0].kwargs["node_input"] == {"action": action.model_dump(), "reviewer_verdict": None}
        assert any("hitl_decision:" in str(item) for item in last_event.output)


@pytest.mark.asyncio
async def test_root_planner_skips_hitl_when_no_proposed_action():
    """Verify root_planner does not invoke hitl_approval_gate when no ProposedAction is drafted."""
    agent = Workflow(
        name="test_root",
        edges=[("START", root_planner)],
    )
    session_service = InMemorySessionService()
    runner = Runner(
        app_name="test_app",
        agent=agent,
        session_service=session_service,
        auto_create_session=True,
    )

    with (
        patch(
            "src.orchestrator.planner.AgentRegistryClient.list_authorized_skills", new_callable=AsyncMock
        ) as mock_list,
        patch("src.orchestrator.planner.emit_skill_invoked_audit"),
        patch("src.orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock) as mock_dispatch,
        patch("src.orchestrator.planner.preload_spending_facts") as mock_preload,
        patch.object(Context, "run_node", new_callable=AsyncMock) as mock_run_node,
    ):
        mock_list.return_value = [
            Skill(name="skills/private-spending-analysis", target_state="TARGET_STATE_ACTIVE", default_revision="v1"),
        ]
        mock_preload.return_value = {}
        mock_dispatch.return_value = {"summary": "spending ok"}

        async def fake_run_node_2(node_func, *args, **kwargs):
            name = getattr(node_func, "name", "")
            if name == "get_skills":
                return ["skills/private-spending-analysis"]
            return None

        mock_run_node.side_effect = fake_run_node_2

        response_stream = runner.run_async(
            user_id="user_hitl_2",
            session_id="sess_hitl_2",
            new_message=UserContent(parts=[Part.from_text(text='{"user_id": "user_hitl_2"}')]),
        )

        events = [e async for e in response_stream]
        hitl_calls = [
            c for c in mock_run_node.call_args_list if c[0] and getattr(c[0][0], "name", "") == "hitl_approval_gate"
        ]
        assert len(hitl_calls) == 0, f"Expected 0 hitl_approval_gate calls, found: {hitl_calls}"


@pytest.mark.asyncio
async def test_root_planner_dispatches_execution_gate_when_hitl_approved():
    """Verify root_planner dispatches execution_gate when HITL decision is approved."""
    agent = Workflow(
        name="test_root",
        edges=[("START", root_planner)],
    )
    session_service = InMemorySessionService()
    runner = Runner(
        app_name="test_app",
        agent=agent,
        session_service=session_service,
        auto_create_session=True,
    )

    with (
        patch(
            "src.orchestrator.planner.AgentRegistryClient.list_authorized_skills", new_callable=AsyncMock
        ) as mock_list,
        patch("src.orchestrator.planner.emit_skill_invoked_audit"),
        patch("src.orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock) as mock_dispatch,
        patch("src.orchestrator.planner.write_proposed_action"),
        patch("src.orchestrator.state.preloader.FirestoreClient") as mock_fs_cls,
        patch.object(Context, "run_node", new_callable=AsyncMock) as mock_run_node,
    ):
        mock_list.return_value = [
            Skill(name="skills/private-action-drafting", target_state="TARGET_STATE_ACTIVE", default_revision="v1"),
        ]

        mock_fs = mock_fs_cls.return_value
        fake_ips = MagicMock(ips_id="ips_1", version=1)
        fake_ips.model_dump.return_value = {"ips_id": "ips_1", "version": 1}
        fake_holdings = MagicMock(total_value_usd=100000.0, positions=[], cash_usd=100000.0)
        fake_holdings.model_dump.return_value = {"total_value_usd": 100000.0, "positions": [], "cash_usd": 100000.0}
        mock_fs.get_active_ips_by_user.return_value = fake_ips
        mock_fs.get_holdings.return_value = fake_holdings

        from datetime import datetime, timezone

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
            action_id="act_exec_1",
            session_id="sess_exec_1",
            type=ActionType.TRADE,
            ticker="AAPL",
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
        mock_dispatch.return_value = action

        hitl_decision = {"outcome": "approved", "action": action.model_dump(), "approving_user_id": "u1"}
        exec_result = {"status": "executed", "broker_order_id": "ord-alp-123", "action_id": "act_exec_1"}

        async def fake_run_node(node_func, *args, **kwargs):
            name = getattr(node_func, "name", "")
            if name == "get_skills":
                return ["skills/private-action-drafting"]
            if name == "hitl_approval_gate":
                return hitl_decision
            if name == "execution_gate":
                return exec_result
            return None

        mock_run_node.side_effect = fake_run_node

        response_stream = runner.run_async(
            user_id="user_exec",
            session_id="sess_exec_1",
            new_message=UserContent(parts=[Part.from_text(text='{"user_id": "user_exec"}')]),
        )

        events = [e async for e in response_stream]
        last_event = events[-1]

        exec_calls = [
            c for c in mock_run_node.call_args_list if c[0] and getattr(c[0][0], "name", "") == "execution_gate"
        ]
        assert len(exec_calls) == 1, f"Expected 1 execution_gate call, found {len(exec_calls)}"
        assert exec_calls[0].kwargs["node_input"] == {"hitl_decision": hitl_decision, "reviewer_verdict": None}
        assert any("execution_result:" in str(item) for item in last_event.output)


@pytest.mark.asyncio
async def test_root_planner_skips_execution_when_hitl_rejected():
    """Verify root_planner dispatches execution_gate which skips when HITL decision is rejected."""
    agent = Workflow(
        name="test_root",
        edges=[("START", root_planner)],
    )
    session_service = InMemorySessionService()
    runner = Runner(
        app_name="test_app",
        agent=agent,
        session_service=session_service,
        auto_create_session=True,
    )

    with (
        patch(
            "src.orchestrator.planner.AgentRegistryClient.list_authorized_skills", new_callable=AsyncMock
        ) as mock_list,
        patch("src.orchestrator.planner.emit_skill_invoked_audit"),
        patch("src.orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock) as mock_dispatch,
        patch("src.orchestrator.planner.write_proposed_action"),
        patch("src.orchestrator.state.preloader.FirestoreClient") as mock_fs_cls,
        patch.object(Context, "run_node", new_callable=AsyncMock) as mock_run_node,
    ):
        mock_list.return_value = [
            Skill(name="skills/private-action-drafting", target_state="TARGET_STATE_ACTIVE", default_revision="v1"),
        ]

        mock_fs = mock_fs_cls.return_value
        fake_ips = MagicMock(ips_id="ips_1", version=1)
        fake_ips.model_dump.return_value = {"ips_id": "ips_1", "version": 1}
        fake_holdings = MagicMock(total_value_usd=100000.0, positions=[], cash_usd=100000.0)
        fake_holdings.model_dump.return_value = {"total_value_usd": 100000.0, "positions": [], "cash_usd": 100000.0}
        mock_fs.get_active_ips_by_user.return_value = fake_ips
        mock_fs.get_holdings.return_value = fake_holdings

        from datetime import datetime, timezone

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
            action_id="act_exec_2",
            session_id="sess_exec_2",
            type=ActionType.TRADE,
            ticker="AAPL",
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
        mock_dispatch.return_value = action

        hitl_decision = {"outcome": "rejected", "action": action.model_dump()}
        exec_result = {"status": "skipped", "reason": "hitl_rejected"}

        async def fake_run_node(node_func, *args, **kwargs):
            name = getattr(node_func, "name", "")
            if name == "get_skills":
                return ["skills/private-action-drafting"]
            if name == "hitl_approval_gate":
                return hitl_decision
            if name == "execution_gate":
                return exec_result
            return None

        mock_run_node.side_effect = fake_run_node

        response_stream = runner.run_async(
            user_id="user_exec_2",
            session_id="sess_exec_2",
            new_message=UserContent(parts=[Part.from_text(text='{"user_id": "user_exec_2"}')]),
        )

        events = [e async for e in response_stream]
        last_event = events[-1]

        exec_calls = [
            c for c in mock_run_node.call_args_list if c[0] and getattr(c[0][0], "name", "") == "execution_gate"
        ]
        assert len(exec_calls) == 1
        assert any("execution_result: {'status': 'skipped'" in str(item) for item in last_event.output)


@pytest.mark.asyncio
async def test_get_skills_from_registry_returns_full_skill_objects():
    from src.orchestrator.planner import get_skills_from_registry

    mock_ctx = MagicMock()
    with patch(
        "src.orchestrator.planner.AgentRegistryClient.list_authorized_skills", new_callable=AsyncMock
    ) as mock_list:
        mock_list.return_value = [
            Skill(
                name="skills/private-goals-onboarding", target_state="TARGET_STATE_ACTIVE", default_revision="rev-goals"
            ),
        ]
        res = await get_skills_from_registry._func(mock_ctx, {})
        assert len(res) == 1
        assert isinstance(res[0], Skill)
        assert res[0].name == "skills/private-goals-onboarding"
        assert res[0].default_revision == "rev-goals"


@pytest.mark.asyncio
async def test_root_planner_threads_registry_entry_id_to_skill_invoked_audit():
    agent = Workflow(
        name="test_root",
        edges=[("START", root_planner)],
    )
    session_service = InMemorySessionService()
    runner = Runner(
        app_name="test_app",
        agent=agent,
        session_service=session_service,
        auto_create_session=True,
    )

    with (
        patch(
            "src.orchestrator.planner.AgentRegistryClient.list_authorized_skills", new_callable=AsyncMock
        ) as mock_list,
        patch("src.orchestrator.planner.emit_skill_invoked_audit") as mock_invoked,
        patch("src.orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock) as mock_dispatch,
        patch("src.orchestrator.planner.preload_spending_facts") as mock_preload,
    ):
        mock_list.return_value = [
            Skill(
                name="skills/private-spending-analysis", target_state="TARGET_STATE_ACTIVE", default_revision="rev-xyz"
            ),
        ]
        mock_preload.return_value = {}
        mock_dispatch.return_value = {"summary": "spending ok"}

        response_stream = runner.run_async(
            user_id="user_trace_1",
            session_id="sess_trace_1",
            new_message=UserContent(parts=[Part.from_text(text='{"user_id": "user_trace_1"}')]),
        )
        _ = [e async for e in response_stream]
        mock_invoked.assert_called_once()
        assert mock_invoked.call_args[1]["registry_entry_id"] == "rev-xyz"


@pytest.mark.asyncio
async def test_root_planner_threads_registry_entry_id_to_action_proposed_audit():
    agent = Workflow(
        name="test_root",
        edges=[("START", root_planner)],
    )
    session_service = InMemorySessionService()
    runner = Runner(
        app_name="test_app",
        agent=agent,
        session_service=session_service,
        auto_create_session=True,
    )

    with (
        patch(
            "src.orchestrator.planner.AgentRegistryClient.list_authorized_skills", new_callable=AsyncMock
        ) as mock_list,
        patch("src.orchestrator.planner.emit_skill_invoked_audit"),
        patch("src.orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock) as mock_dispatch,
        patch("src.orchestrator.planner.write_proposed_action") as mock_write,
        patch("src.orchestrator.state.preloader.FirestoreClient") as mock_fs_cls,
        patch("src.orchestrator.gates.hitl.FirestoreClient"),
        patch("src.orchestrator.state.writers.FirestoreClient"),
    ):
        mock_list.return_value = [
            Skill(
                name="skills/private-action-drafting",
                target_state="TARGET_STATE_ACTIVE",
                default_revision="rev-action-99",
            ),
        ]
        mock_fs = mock_fs_cls.return_value
        fake_ips = MagicMock(ips_id="ips_1", version=1)
        fake_ips.model_dump.return_value = {"ips_id": "ips_1", "version": 1}
        fake_holdings = MagicMock(total_value_usd=100000.0, positions=[], cash_usd=100000.0)
        fake_holdings.model_dump.return_value = {"total_value_usd": 100000.0, "positions": [], "cash_usd": 100000.0}
        mock_fs.get_active_ips_by_user.return_value = fake_ips
        mock_fs.get_holdings.return_value = fake_holdings

        from datetime import datetime, timezone

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
            action_id="act_trace_1",
            session_id="sess_trace_1",
            type=ActionType.TRADE,
            ticker="AAPL",
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
        mock_dispatch.return_value = action

        response_stream = runner.run_async(
            user_id="user_trace_2",
            session_id="sess_trace_2",
            new_message=UserContent(parts=[Part.from_text(text='{"user_id": "user_trace_2"}')]),
        )
        _ = [e async for e in response_stream]
        mock_write.assert_called_once()
        assert mock_write.call_args[1]["registry_entry_id"] == "rev-action-99"


@pytest.mark.asyncio
async def test_root_planner_threads_registry_entry_id_to_goals_onboarding_write():
    agent = Workflow(
        name="test_root",
        edges=[("START", root_planner)],
    )
    session_service = InMemorySessionService()
    runner = Runner(
        app_name="test_app",
        agent=agent,
        session_service=session_service,
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
        mock_list.return_value = [
            Skill(
                name="skills/private-goals-onboarding",
                target_state="TARGET_STATE_ACTIVE",
                default_revision="rev-goals-77",
            ),
        ]
        mock_write.return_value = (
            MagicMock(ips_id="ips-77", version=1, risk_tolerance=RiskTolerance.MODERATE, time_horizon_years=10),
            MagicMock(),
        )
        mock_dispatch.return_value = GoalsOnboardingResult(
            user_id="u_trace_3",
            primary_goal=Goal(name="House", target_amount_usd=200000.0, target_date="2030-01-01"),
            risk_tolerance=RiskTolerance.MODERATE,
            time_horizon_years=5,
            target_allocation=[],
            interview_summary="Onboarding complete",
        )

        response_stream = runner.run_async(
            user_id="u_trace_3",
            session_id="sess_trace_3",
            new_message=UserContent(parts=[Part.from_text(text='{"user_id": "u_trace_3", "trigger": "initial"}')]),
        )
        _ = [e async for e in response_stream]
        mock_write.assert_called_once()
        assert mock_write.call_args[1]["registry_entry_id"] == "rev-goals-77"


def test_reviewer_skips_when_no_drafted_action():
    from src.orchestrator.planner import SKILL_PLANS

    plan = SKILL_PLANS["private-reviewer"]
    assert plan.build_input("user_1", {}, {}) is None
    assert plan.build_input("user_1", {}, {"action_drafting_result": {"status": "executed"}}) is None


@patch("src.orchestrator.planner.preload_for_reviewer")
def test_reviewer_builds_input_when_drafted_action_present(mock_preload):
    from src.orchestrator.planner import SKILL_PLANS

    mock_preload.return_value = {"action": "test"}
    plan = SKILL_PLANS["private-reviewer"]
    ctx = {"action_drafting_result": {"status": "drafted", "action_id": "a_1"}}
    inp = {}
    res = plan.build_input("user_1", inp, ctx)
    assert res == {"action": "test"}
    assert inp["_reviewer_action"] == ctx["action_drafting_result"]
    mock_preload.assert_called_once_with(user_id="user_1", action=ctx["action_drafting_result"])


@pytest.mark.asyncio
@patch("src.orchestrator.planner.FirestoreClient")
@patch("src.orchestrator.planner.emit_review_completed_audit")
async def test_reviewer_postprocess_populates_context(mock_emit, mock_fs_cls):
    from datetime import datetime, timezone

    from src.orchestrator.contracts import (
        ActionStatus,
        ActionType,
        Constraints,
        InvestmentPolicyStatement,
        IPSStatus,
        OrderType,
        ProposedAction,
        RelatedIPSVersion,
        RiskTolerance,
        Side,
        SkillVersionRef,
        TargetAllocation,
    )
    from src.orchestrator.contracts.holdings import HoldingsSnapshot, Position
    from src.orchestrator.contracts.reviewer_verdict import ReviewerVerdict, RuleResult
    from src.orchestrator.planner import SKILL_PLANS

    mock_fs = mock_fs_cls.return_value
    fake_ips = InvestmentPolicyStatement(
        ips_id="ips_1",
        user_id="user_1",
        version=1,
        status=IPSStatus.ACTIVE,
        effective_date="2026-01-01",
        risk_tolerance=RiskTolerance.MODERATE,
        time_horizon_years=10,
        target_allocation=[TargetAllocation(asset_class="Equity", target_percent=60, min_percent=50, max_percent=70)],
        constraints=Constraints(concentration_limit_percent=15, excluded_tickers=[], excluded_sectors=[]),
        approval_required_above_usd=25000.0,
        approval_required_above_percent=20.0,
        created_at=datetime.now(timezone.utc),
    )
    fake_holdings = HoldingsSnapshot(
        user_id="user_1",
        as_of=datetime.now(timezone.utc),
        positions=[Position(ticker="AAPL", quantity=10, asset_class="Equity", market_value_usd=10000.0)],
        cash_usd=90000.0,
        total_value_usd=100000.0,
    )
    mock_fs.get_active_ips_by_user.return_value = fake_ips
    mock_fs.get_holdings.return_value = fake_holdings

    action = ProposedAction(
        action_id="act_1",
        session_id="s_1",
        type=ActionType.TRADE,
        ticker="AAPL",
        side=Side.BUY,
        quantity=5.0,
        order_type=OrderType.MARKET,
        estimated_price_usd=200.0,
        estimated_value_usd=1000.0,
        rationale="test",
        supporting_research_refs=[],
        ips_version_referenced=RelatedIPSVersion(ips_id="ips_1", version=1),
        proposed_by_skill_version=SkillVersionRef(skill_name="private-action-drafting", skill_version="0.1.0"),
        status=ActionStatus.DRAFTED,
        created_at=datetime.now(timezone.utc),
    )
    llm_verdict = ReviewerVerdict(
        verdict_id="v_llm",
        action_id="act_1",
        ips_version_checked_against=RelatedIPSVersion(ips_id="ips_1", version=1),
        rule_results=[RuleResult(rule_id="excluded_ticker", description="test", passed=True)],
        overall_pass=True,
        requires_human_approval=False,
        reviewer_skill_version=SkillVersionRef(skill_name="private-reviewer", skill_version="0.1.0"),
        reviewed_at=datetime.now(timezone.utc),
    )

    plan = SKILL_PLANS["private-reviewer"]
    inp = {"_reviewer_action": action.model_dump()}
    payload, ctx_update = await plan.postprocess("user_1", llm_verdict, {}, inp, registry_entry_id="rev-rev-1")
    assert ctx_update["reviewer_verdict"].overall_pass is True
    assert ctx_update["reviewer_verdict_llm"].verdict_id == "v_llm"
    mock_emit.assert_called_once()
    assert mock_emit.call_args[1]["registry_entry_id"] == "rev-rev-1"


@pytest.mark.asyncio
@patch("src.orchestrator.planner.emit_review_completed_audit")
@patch("src.orchestrator.planner.FirestoreClient")
@patch("src.orchestrator.state.preloader.FirestoreClient")
async def test_reviewer_build_input_mirrors_preloaded_state_into_input_dict(
    mock_preload_fs_cls, mock_planner_fs_cls, mock_emit
):
    """Verify build_input mirrors the preloader's IPS + holdings into input_dict so
    postprocess reuses them and never re-reads Firestore."""
    from datetime import date, datetime, timezone

    from src.orchestrator.contracts.holdings import HoldingsSnapshot, Position
    from src.orchestrator.contracts.ips import (
        Constraints,
        InvestmentPolicyStatement,
        IPSStatus,
        RiskTolerance,
        TargetAllocation,
    )
    from src.orchestrator.contracts.proposed_action import (
        ActionStatus,
        ActionType,
        OrderType,
        ProposedAction,
        RelatedIPSVersion,
        Side,
        SkillVersionRef,
    )
    from src.orchestrator.planner import SKILL_PLANS

    fake_ips = InvestmentPolicyStatement(
        ips_id="ips_pre",
        user_id="user_pre",
        version=1,
        status=IPSStatus.ACTIVE,
        effective_date=date(2026, 1, 1),
        risk_tolerance=RiskTolerance.MODERATE,
        time_horizon_years=10,
        target_allocation=[TargetAllocation(asset_class="Equity", target_percent=60, min_percent=50, max_percent=70)],
        constraints=Constraints(concentration_limit_percent=15, excluded_tickers=[], excluded_sectors=[]),
        approval_required_above_usd=25000.0,
        approval_required_above_percent=20.0,
        created_at=datetime.now(timezone.utc),
    )
    fake_holdings = HoldingsSnapshot(
        user_id="user_pre",
        as_of=datetime.now(timezone.utc),
        positions=[Position(ticker="AAPL", quantity=10, asset_class="Equity", market_value_usd=10000.0)],
        cash_usd=90000.0,
        total_value_usd=100000.0,
    )

    action = ProposedAction(
        action_id="act_pre",
        session_id="s_1",
        type=ActionType.TRADE,
        ticker="AAPL",
        side=Side.BUY,
        quantity=5.0,
        order_type=OrderType.MARKET,
        estimated_price_usd=200.0,
        estimated_value_usd=1000.0,
        rationale="test",
        supporting_research_refs=[],
        ips_version_referenced=RelatedIPSVersion(ips_id="ips_pre", version=1),
        proposed_by_skill_version=SkillVersionRef(skill_name="private-action-drafting", skill_version="0.1.0"),
        status=ActionStatus.DRAFTED,
        created_at=datetime.now(timezone.utc),
    )

    # Preloader's Firestore returns the fake state; the planner's Firestore must never be
    # touched during postprocess (that's the whole point of the refactor).
    preload_fs = mock_preload_fs_cls.return_value
    preload_fs.get_active_ips_by_user.return_value = fake_ips
    preload_fs.get_holdings.return_value = fake_holdings

    plan = SKILL_PLANS["private-reviewer"]
    input_dict: dict = {}
    context = {"action_drafting_result": {**action.model_dump(), "status": "drafted"}}

    node_input = plan.build_input("user_pre", input_dict, context)
    assert node_input is not None
    # build_input must mirror the preloader's IPS + holdings into input_dict.
    assert input_dict["_preloaded_ips"] == fake_ips.model_dump(mode="json")
    assert input_dict["_preloaded_holdings"] == fake_holdings.model_dump(mode="json")

    # Now postprocess reads them from input_dict — no second Firestore round-trip.
    planner_fs = mock_planner_fs_cls.return_value
    payload, ctx_update = await plan.postprocess("user_pre", None, {}, input_dict, registry_entry_id="rev-1")
    assert ctx_update["reviewer_verdict"].action_id == "act_pre"
    planner_fs.get_active_ips_by_user.assert_not_called()
    planner_fs.get_holdings.assert_not_called()


@pytest.mark.asyncio
@patch("src.orchestrator.planner.write_proposed_action")
@patch("src.orchestrator.state.preloader.FirestoreClient")
async def test_action_drafting_stamps_active_ips_version_from_rationale(mock_preload_fs_cls, mock_write):
    """Regression: when action-drafting's Managed Agent returns a ProposedActionRationale
    (the real production schema), the orchestrator builds the ProposedAction from the
    precomputed trade and must stamp ips_version_referenced with the *active* IPS
    (not the "ips_unknown" sentinel). A wrong id makes the reviewer's
    ips_version_current rule fail and wrongly rejects a compliant trade."""
    from datetime import date, datetime, timezone

    from src.orchestrator.contracts.holdings import HoldingsSnapshot, Position
    from src.orchestrator.contracts.ips import (
        Constraints,
        InvestmentPolicyStatement,
        IPSStatus,
        RiskTolerance,
        TargetAllocation,
    )
    from src.orchestrator.contracts.proposed_action import ProposedAction, ProposedActionRationale
    from src.orchestrator.planner import SKILL_PLANS

    fake_ips = InvestmentPolicyStatement(
        ips_id="ips_active_42",
        user_id="user_ad",
        version=3,
        status=IPSStatus.ACTIVE,
        effective_date=date(2026, 1, 1),
        risk_tolerance=RiskTolerance.MODERATE,
        time_horizon_years=10,
        target_allocation=[TargetAllocation(asset_class="Equity", target_percent=60, min_percent=50, max_percent=70)],
        constraints=Constraints(concentration_limit_percent=90, excluded_tickers=[], excluded_sectors=[]),
        created_at=datetime.now(timezone.utc),
    )
    fake_holdings = HoldingsSnapshot(
        user_id="user_ad",
        as_of=datetime.now(timezone.utc),
        positions=[Position(ticker="AAPL", quantity=100, asset_class="Equity", market_value_usd=80000.0)],
        cash_usd=20000.0,
        total_value_usd=100000.0,
    )
    preload_fs = mock_preload_fs_cls.return_value
    preload_fs.get_active_ips_by_user.return_value = fake_ips
    preload_fs.get_holdings.return_value = fake_holdings

    plan = SKILL_PLANS["private-action-drafting"]
    # A direct user-requested sell produces a deterministic precomputed_trade.
    input_dict: dict = {"requested_trade": {"ticker": "AAPL", "side": "sell", "quantity": 5}}

    node_input = plan.build_input("user_ad", input_dict, {})
    assert node_input is not None
    assert node_input.get("precomputed_trade") is not None
    # build_input must mirror the preloaded active IPS into input_dict.
    assert input_dict.get("ips", {}).get("ips_id") == "ips_active_42"
    # _execute_skill mirrors the precomputed trade into input_dict before postprocess.
    input_dict.setdefault("precomputed_trade", node_input.get("precomputed_trade"))
    # The Managed Agent returns only the narrow rationale slice in production.
    rationale = ProposedActionRationale(rationale="Trim per user request.", supporting_research_refs=[])

    payload, _ = await plan.postprocess("user_ad", rationale, MagicMock(), input_dict, registry_entry_id="rev-9")

    action = ProposedAction.model_validate(payload)
    assert action.ips_version_referenced.ips_id == "ips_active_42"
    assert action.ips_version_referenced.version == 3
    mock_write.assert_called_once()


@patch("src.orchestrator.planner.emit_skill_revoked_audit")
def test_detect_revocations_emits_for_missing_skills(mock_emit):
    from src.orchestrator.planner import _detect_and_audit_revocations

    ctx = MagicMock()
    ctx.state = {
        "last_authorized_skills": [
            {"name": "skills/private-A", "default_revision": "rev-A1"},
            {"name": "skills/private-B", "default_revision": "rev-B1"},
        ]
    }
    current_skills = [MagicMock(name="skills/private-A", default_revision="rev-A1")]
    # override .name attribute on mock
    current_skills[0].name = "skills/private-A"

    _detect_and_audit_revocations(ctx, current_skills)
    mock_emit.assert_called_once()
    assert mock_emit.call_args[1]["revoked_skill_short_name"] in ("B", "private-B")
    assert mock_emit.call_args[1]["prior_registry_entry_id"] == "rev-B1"
    assert ctx.state["last_authorized_skills"] == [{"name": "skills/private-A", "default_revision": "rev-A1"}]


@patch("src.orchestrator.planner.emit_skill_revoked_audit")
def test_detect_revocations_first_cycle_no_prior_state(mock_emit):
    from src.orchestrator.planner import _detect_and_audit_revocations

    ctx = MagicMock()
    ctx.state = {}
    current_skills = [MagicMock()]
    current_skills[0].name = "skills/private-A"
    current_skills[0].default_revision = "rev-A1"

    _detect_and_audit_revocations(ctx, current_skills)
    mock_emit.assert_not_called()
    assert ctx.state["last_authorized_skills"] == [{"name": "skills/private-A", "default_revision": "rev-A1"}]


@patch("src.orchestrator.planner.emit_skill_revoked_audit")
def test_detect_revocations_audit_failure_does_not_abort_detection(mock_emit):
    from src.orchestrator.planner import _detect_and_audit_revocations

    ctx = MagicMock()
    ctx.state = {
        "last_authorized_skills": [
            {"name": "skills/private-A", "default_revision": "rev-A"},
            {"name": "skills/private-B", "default_revision": "rev-B"},
        ]
    }

    mock_emit.side_effect = [Exception("error"), None]
    _detect_and_audit_revocations(ctx, [])
    assert mock_emit.call_count == 2
    assert ctx.state["last_authorized_skills"] == []


@pytest.mark.asyncio
@patch("src.orchestrator.planner.emit_skill_revoked_audit")
@patch("src.orchestrator.planner.emit_skill_invoked_audit")
@patch("src.orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock)
@patch("src.orchestrator.planner.preload_spending_facts")
@patch("src.orchestrator.planner.AgentRegistryClient")
async def test_root_planner_end_to_end_second_cycle_omits_revoked_skill(
    mock_reg_cls, mock_preload, mock_dispatch, mock_invoked, mock_emit
):
    from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
    from google.adk.runners import Runner
    from google.adk.sessions.in_memory_session_service import InMemorySessionService

    from src.orchestrator.planner import root_agent
    from src.orchestrator.registry_client import Skill

    skill_a = Skill(
        name="projects/test/locations/global/skills/private-spending-analysis",
        target_state="TARGET_STATE_ACTIVE",
        default_revision="rev-spend-1",
    )
    skill_b = Skill(
        name="projects/test/locations/global/skills/private-goals-onboarding",
        target_state="TARGET_STATE_ACTIVE",
        default_revision="rev-goal-1",
    )

    # Cycle 1 returns [A, B], cycle 2 returns [A] (B was revoked)
    mock_reg_cls.return_value.list_authorized_skills = AsyncMock(side_effect=[[skill_a, skill_b], [skill_a]])
    mock_preload.return_value = {}
    mock_dispatch.return_value = {"summary": "ok"}

    runner = Runner(
        app_name="test_revocation",
        agent=root_agent,
        session_service=InMemorySessionService(),
        memory_service=InMemoryMemoryService(),
        auto_create_session=True,
    )

    # Cycle 1
    stream1 = runner.run_async(
        user_id="user_1",
        session_id="sess_1",
        new_message=UserContent(parts=[Part.from_text(text="{}")]),
    )
    res1 = [e async for e in stream1]

    # Cycle 2
    stream2 = runner.run_async(
        user_id="user_1",
        session_id="sess_1",
        new_message=UserContent(parts=[Part.from_text(text="{}")]),
    )
    res2 = [e async for e in stream2]

    # Check that emit_skill_revoked_audit was called for B
    mock_emit.assert_called_once()
    assert mock_emit.call_args[1]["revoked_skill_short_name"] in ("goals-onboarding", "private-goals-onboarding")
    assert mock_emit.call_args[1]["prior_registry_entry_id"] == "rev-goal-1"


@pytest.mark.asyncio
async def test_root_planner_runs_research_and_portfolio_analysis_in_parallel():
    import asyncio
    import time

    from orchestrator.contracts.drift_report import DriftReport
    from orchestrator.contracts.research_brief import ConfidenceLevel, ResearchBrief

    skill_pa = Skill(
        name="projects/test/locations/global/skills/private-portfolio-analysis",
        target_state="TARGET_STATE_ACTIVE",
        default_revision="rev-pa-1",
    )
    skill_res = Skill(
        name="projects/test/locations/global/skills/private-research",
        target_state="TARGET_STATE_ACTIVE",
        default_revision="rev-res-1",
    )

    starts = {}
    ends = {}

    async def fake_dispatch(skill_name: str, **kwargs):
        starts[skill_name] = time.monotonic()
        await asyncio.sleep(0.05)
        ends[skill_name] = time.monotonic()
        if "portfolio-analysis" in skill_name:
            return DriftReport(entries=[], unclassified_value_usd=0.0, rebalance_recommended=False)
        if "research" in skill_name:
            return ResearchBrief(
                research_run_id="run_p",
                query="market outlook",
                summary="Stable.",
                sources=[],
                confidence=ConfidenceLevel.HIGH,
                as_of=1700000000,
            )
        return {}

    with (
        patch(
            "src.orchestrator.planner.AgentRegistryClient.list_authorized_skills", new_callable=AsyncMock
        ) as mock_list,
        patch("src.orchestrator.planner.dispatch_managed_skill", side_effect=fake_dispatch),
        patch("src.orchestrator.planner.emit_skill_invoked_audit"),
        patch("src.orchestrator.planner.preload_for_portfolio_analysis", return_value={"user_id": "u1"}),
        patch(
            "src.orchestrator.planner.preload_for_research",
            return_value={"user_id": "u1", "research_question": "market outlook"},
        ),
        patch("src.orchestrator.state.preloader.preload_for_portfolio_analysis", return_value={"user_id": "u1"}),
        patch(
            "src.orchestrator.state.preloader.preload_for_research",
            return_value={"user_id": "u1", "research_question": "market outlook"},
        ),
        patch("src.orchestrator.data.firestore.FirestoreClient"),
        patch("src.orchestrator.state.writers.FirestoreClient"),
        patch("orchestrator.state.writers.FirestoreClient", create=True),
    ):
        mock_list.return_value = [skill_pa, skill_res]

        root_agent = Workflow(
            name="test_parallel",
            edges=[("START", root_planner)],
        )
        runner = Runner(
            app_name="test_parallel",
            agent=root_agent,
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
            auto_create_session=True,
        )

        stream = runner.run_async(
            user_id="user_1",
            session_id="sess_1",
            new_message=UserContent(
                parts=[Part.from_text(text='{"user_id": "user_1", "research_question": "market outlook"}')]
            ),
        )
        _ = [e async for e in stream]

        # Both skills ran and their execution windows overlapped in time
        assert "portfolio-analysis" in starts or "private-portfolio-analysis" in starts
        assert "research" in starts or "private-research" in starts
        pa_name = "private-portfolio-analysis" if "private-portfolio-analysis" in starts else "portfolio-analysis"
        res_name = "private-research" if "private-research" in starts else "research"

        assert starts[res_name] < ends[pa_name]
        assert starts[pa_name] < ends[res_name]


@pytest.mark.asyncio
@patch("src.orchestrator.planner.write_ips_from_interview_result")
async def test_postprocess_goals_onboarding_adds_adk_event_to_memory(mock_write):
    from google.adk.events import Event

    from src.orchestrator.planner import _postprocess_goals_onboarding

    mock_ips = MagicMock(
        ips_id="ips-123",
        version=1,
        risk_tolerance=RiskTolerance.MODERATE,
        time_horizon_years=10,
    )
    mock_write.return_value = (mock_ips, MagicMock())

    result = GoalsOnboardingResult(
        user_id="user_test_memory",
        primary_goal=Goal(name="Retirement", target_amount_usd=1000000.0, target_date="2045-01-01"),
        risk_tolerance=RiskTolerance.MODERATE,
        time_horizon_years=10,
        target_allocation=[],
        interview_summary="User seeks moderate growth over 10 years.",
    )

    mock_ctx = AsyncMock(spec=Context)

    payload, update = await _postprocess_goals_onboarding(
        user_id="user_test_memory",
        result=result,
        ctx=mock_ctx,
        input_dict={"trigger": "initial"},
    )

    assert payload["status"] == "completed"
    assert payload["ips_id"] == "ips-123"
    mock_ctx.add_events_to_memory.assert_awaited_once()
    called_events = mock_ctx.add_events_to_memory.await_args.kwargs.get("events")
    assert len(called_events) == 1
    event = called_events[0]
    assert isinstance(event, Event)
    assert hasattr(event, "content")
    assert isinstance(event.content, UserContent)
    assert "User user_test_memory completed goals onboarding" in event.content.parts[0].text
