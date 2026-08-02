import pytest
from google.adk import Context
from google.adk.events import RequestInput
from google.adk.workflow import node, Workflow
from google.adk.runners import Runner
from unittest.mock import patch, AsyncMock, MagicMock
from src.orchestrator.registry_client import Skill
from src.orchestrator.planner import root_planner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from typing import Any
from google.genai.types import UserContent, Part

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
    runner = Runner(app_name="test_app", agent=agent, session_service=session_service, memory_service=memory_service, auto_create_session=True)

    session_id = "test_session_123"

    # --- FIRST RUN ---
    response_stream = runner.run_async(user_id="user_123", session_id=session_id, new_message=UserContent(parts=[Part.from_text(text="start_goal")]))

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
    response_stream = runner.run_async(
        user_id="user_123",
        session_id=session_id,
        invocation_id=last_event.invocation_id,
        new_message=UserContent(parts=[Part.from_function_response(name="adk_request_input", response={"interruptId": interrupt_id, "payload": "approved"})])
    )

    events2 = []
    async for event in response_stream:
        events2.append(event)

    if events2:
        assert events2[-1].output == {"count": "Count: 1", "approval": "approved"}

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
    runner = Runner(app_name="test_app", agent=agent, session_service=session_service, memory_service=memory_service, auto_create_session=True)

    with patch("src.orchestrator.planner.AgentRegistryClient.list_authorized_skills", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = [
            Skill(name="projects/test-project/locations/test-location/skills/research", target_state="TARGET_STATE_ACTIVE", default_revision="rev1"),
            Skill(name="projects/test-project/locations/test-location/skills/action_drafting", target_state="TARGET_STATE_ACTIVE", default_revision="rev2"),
        ]

        response_stream = runner.run_async(user_id="user_123", session_id="session_456", new_message=UserContent(parts=[Part.from_text(text="test_goal")]))

        events = []
        async for event in response_stream:
            events.append(event)

        last_event = events[-1]
        assert last_event.output == [
            "projects/test-project/locations/test-location/skills/research_completed",
            "projects/test-project/locations/test-location/skills/action_drafting_completed",
        ]


@pytest.mark.asyncio
async def test_root_planner_json_input():
    agent = Workflow(
        name="test_root",
        edges=[("START", root_planner)],
    )
    session_service = InMemorySessionService()
    memory_service = InMemoryMemoryService()
    runner = Runner(app_name="test_app", agent=agent, session_service=session_service, memory_service=memory_service, auto_create_session=True)

    with patch("src.orchestrator.planner.AgentRegistryClient.list_authorized_skills", new_callable=AsyncMock) as mock_list, \
         patch("src.orchestrator.skills.goals_onboarding.FirestoreClient") as mock_db:

        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance

        mock_list.return_value = [
            Skill(name="projects/test-project/locations/test-location/skills/private-goals-onboarding", target_state="TARGET_STATE_ACTIVE", default_revision="rev1"),
        ]

        # Use valid json input payload as string text part to cover that branch properly
        response_stream = runner.run_async(user_id="user_123", session_id="session_456", new_message=UserContent(parts=[Part.from_text(text='{"user_id": "u4", "trigger": "initial"}')]))

        events = []
        async for event in response_stream:
            events.append(event)

        def has_request_input(e):
             if e.content and e.content.parts:
                  for p in e.content.parts:
                       if p.function_call and p.function_call.name == "adk_request_input":
                            return True
             return False

        assert any(has_request_input(e) for e in events)


@pytest.mark.asyncio
async def test_root_planner_dispatches_goals_onboarding_with_realistic_name():
    """Verify planner extracts short name from full resource path and invokes goals_onboarding_skill."""
    agent = Workflow(
        name="test_root",
        edges=[("START", root_planner)],
    )
    session_service = InMemorySessionService()
    memory_service = InMemoryMemoryService()
    runner = Runner(app_name="test_app", agent=agent, session_service=session_service, memory_service=memory_service, auto_create_session=True)

    with patch("src.orchestrator.planner.AgentRegistryClient.list_authorized_skills", new_callable=AsyncMock) as mock_list, \
         patch("src.orchestrator.skills.goals_onboarding.FirestoreClient") as mock_db:

        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance

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

        def has_request_input(e):
            if e.content and e.content.parts:
                for p in e.content.parts:
                    if p.function_call and p.function_call.name == "adk_request_input":
                        return True
            return False

        assert any(has_request_input(e) for e in events)


@pytest.mark.asyncio
async def test_root_planner_invalid_json():
    import asyncio
    from google.adk.workflow import Workflow
    from google.adk.runners import Runner

    agent = Workflow(
        name="test_root",
        edges=[("START", root_planner)],
    )

    session_service = InMemorySessionService()
    runner = Runner(app_name="test_app", agent=agent, session_service=session_service, auto_create_session=True)

    with patch("src.orchestrator.planner.AgentRegistryClient.list_authorized_skills", new_callable=AsyncMock) as mock_list, \
         patch("src.orchestrator.skills.goals_onboarding.FirestoreClient") as mock_db:

        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance
        mock_list.return_value = [
            Skill(name="projects/test-project/locations/test-location/skills/private-goals-onboarding", target_state="TARGET_STATE_ACTIVE", default_revision="rev1")
        ]

        response_stream = runner.run_async(user_id="user_123", session_id="s1", new_message=UserContent(parts=[Part.from_text(text="invalid json {")]))
        events = [e async for e in response_stream]
        assert len(events) > 0
