from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.workflow import Workflow, node
from google.genai.types import Part, UserContent

from orchestrator.contracts.hitl_decision import HITLOutcome
from orchestrator.contracts.ips import RelatedIPSVersion
from orchestrator.contracts.proposed_action import (
    ActionStatus,
    ActionType,
    OrderType,
    ProposedAction,
    Side,
    SkillVersionRef,
)
from orchestrator.contracts.reviewer_verdict import ReviewerVerdict, RuleResult
from orchestrator.gates.hitl import hitl_approval_gate


@pytest.fixture
def sample_proposed_action():
    return ProposedAction(
        action_id="act-test-123",
        session_id="sess-123",
        type=ActionType.TRADE,
        ticker="AAPL",
        side=Side.BUY,
        quantity=5,
        order_type=OrderType.LIMIT,
        limit_price_usd=150.0,
        estimated_price_usd=150.0,
        estimated_value_usd=750.0,
        rationale="Rebalancing into equity",
        ips_version_referenced=RelatedIPSVersion(ips_id="ips-1", version=1),
        proposed_by_skill_version=SkillVersionRef(skill_name="action-drafting", skill_version="0.1.0"),
        status=ActionStatus.DRAFTED,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_reviewer_verdict():
    return ReviewerVerdict(
        verdict_id="verdict-123",
        action_id="act-test-123",
        ips_version_checked_against=RelatedIPSVersion(ips_id="ips-1", version=1),
        rule_results=[RuleResult(rule_id="r1", description="rule 1", passed=True)],
        overall_pass=True,
        requires_human_approval=True,
        reviewer_skill_version=SkillVersionRef(skill_name="reviewer", skill_version="0.1.0"),
        reviewed_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_firestore_client():
    client = MagicMock()
    with (
        patch("orchestrator.gates.hitl.FirestoreClient", return_value=client),
        patch("orchestrator.gates.hitl.emit_approval_requested_audit"),
        patch("orchestrator.gates.hitl.emit_approval_granted_audit"),
        patch("orchestrator.gates.hitl.emit_approval_rejected_audit"),
    ):
        yield client


@node(name="hitl_test_root", rerun_on_resume=True)
async def hitl_test_root(ctx, node_input):
    return await ctx.run_node(hitl_approval_gate, node_input=node_input)


def _create_gate_workflow():
    return Workflow(
        name="test_hitl_workflow",
        description="Minimal workflow wrapping hitl_approval_gate",
        edges=[("START", hitl_test_root)],
    )


def _get_request_input_interrupt(last_event):
    parts = last_event.content.parts if last_event.content and last_event.content.parts else []
    for part in parts:
        if part.function_call and part.function_call.name == "adk_request_input":
            args = dict(part.function_call.args)
            msg = args.get("message")
            if isinstance(msg, str):
                try:
                    args["message"] = json.loads(msg)
                except Exception:
                    pass
            return part.function_call.id, args
    return None, None


import json


async def _run_runner(runner, session_id, message, invocation_id=None):
    if not isinstance(message, UserContent):
        if isinstance(message, Part):
            message = UserContent(parts=[message])
        elif isinstance(message, dict):
            message = UserContent(parts=[Part.from_text(text=json.dumps(message, default=str))])
        else:
            message = UserContent(parts=[Part.from_text(text=str(message))])
    events = []
    stream = runner.run_async(
        user_id="test_user",
        session_id=session_id,
        new_message=message,
        invocation_id=invocation_id,
    )
    async for event in stream:
        events.append(event)
    return events


@pytest.mark.asyncio
async def test_gate_yields_request_input_with_structured_payload(
    sample_proposed_action, sample_reviewer_verdict, mock_firestore_client
):
    workflow = _create_gate_workflow()
    runner = Runner(
        agent=workflow,
        app_name="test_app",
        session_service=InMemorySessionService(),
        auto_create_session=True,
    )

    events = await _run_runner(
        runner,
        "test_session",
        {"action": sample_proposed_action.model_dump(), "reviewer_verdict": sample_reviewer_verdict.model_dump()},
    )

    last_event = events[-1]
    interrupt_id, args = _get_request_input_interrupt(last_event)
    assert interrupt_id is not None
    payload = args.get("message")
    assert payload["kind"] == "hitl_approval_request"
    assert payload["action"]["action_id"] == "act-test-123"
    assert payload["reviewer_verdict"]["verdict_id"] == "verdict-123"
    assert payload["allowed_decisions"] == ["approve", "edit", "reject"]


@pytest.mark.asyncio
async def test_gate_approve_returns_approved_decision(
    sample_proposed_action, sample_reviewer_verdict, mock_firestore_client
):
    workflow = _create_gate_workflow()
    runner = Runner(
        agent=workflow,
        app_name="test_app",
        session_service=InMemorySessionService(),
        auto_create_session=True,
    )

    events1 = await _run_runner(
        runner,
        "test_session",
        {"action": sample_proposed_action.model_dump(), "reviewer_verdict": sample_reviewer_verdict.model_dump()},
    )
    last_event = events1[-1]
    interrupt_id, _ = _get_request_input_interrupt(last_event)

    response_part = Part.from_function_response(
        name="adk_request_input",
        response={"interruptId": interrupt_id, "payload": {"decision": "approve", "user_id": "u1"}},
    )
    response_part.function_response.id = interrupt_id

    events2 = await _run_runner(
        runner,
        "test_session",
        response_part,
        invocation_id=last_event.invocation_id,
    )

    final_event = events2[-1]
    result = final_event.output
    assert result["outcome"] == HITLOutcome.APPROVED.value
    assert result["approving_user_id"] == "u1"
    mock_firestore_client.update_proposed_action_status.assert_called_once_with(
        "act-test-123", ActionStatus.APPROVED
    )


@pytest.mark.asyncio
async def test_gate_reject_returns_rejected_decision(
    sample_proposed_action, sample_reviewer_verdict, mock_firestore_client
):
    workflow = _create_gate_workflow()
    runner = Runner(
        agent=workflow,
        app_name="test_app",
        session_service=InMemorySessionService(),
        auto_create_session=True,
    )

    events1 = await _run_runner(
        runner,
        "test_session",
        {"action": sample_proposed_action.model_dump(), "reviewer_verdict": sample_reviewer_verdict.model_dump()},
    )
    last_event = events1[-1]
    interrupt_id, _ = _get_request_input_interrupt(last_event)

    response_part = Part.from_function_response(
        name="adk_request_input",
        response={"interruptId": interrupt_id, "payload": {"decision": "reject", "reason": "too risky", "user_id": "u1"}},
    )
    response_part.function_response.id = interrupt_id

    events2 = await _run_runner(
        runner,
        "test_session",
        response_part,
        invocation_id=last_event.invocation_id,
    )

    final_event = events2[-1]
    result = final_event.output
    assert result["outcome"] == HITLOutcome.REJECTED.value
    assert result["reason"] == "too risky"
    mock_firestore_client.update_proposed_action_status.assert_called_once_with(
        "act-test-123", ActionStatus.REJECTED
    )


@pytest.mark.asyncio
async def test_gate_edit_then_approve_completes_after_one_round(
    sample_proposed_action, mock_firestore_client
):
    workflow = _create_gate_workflow()
    runner = Runner(
        agent=workflow,
        app_name="test_app",
        session_service=InMemorySessionService(),
        auto_create_session=True,
    )

    events1 = await _run_runner(
        runner,
        "test_session",
        {"action": sample_proposed_action.model_dump(), "reviewer_verdict": None},
    )
    last_event1 = events1[-1]
    interrupt_id1, _ = _get_request_input_interrupt(last_event1)

    # First resume: edit quantity to 10
    response_part1 = Part.from_function_response(
        name="adk_request_input",
        response={"interruptId": interrupt_id1, "payload": {"decision": "edit", "changes": {"quantity": 10}, "user_id": "u1"}},
    )
    response_part1.function_response.id = interrupt_id1

    events2 = await _run_runner(
        runner,
        "test_session",
        response_part1,
        invocation_id=last_event1.invocation_id,
    )
    last_event2 = events2[-1]
    interrupt_id2, args2 = _get_request_input_interrupt(last_event2)
    assert interrupt_id2 is not None
    payload2 = args2.get("message")
    assert payload2["action"]["quantity"] == 10
    assert payload2["edit_round"] == 1
    mock_firestore_client.set_proposed_action.assert_called_once()

    # Second resume: approve
    response_part2 = Part.from_function_response(
        name="adk_request_input",
        response={"interruptId": interrupt_id2, "payload": {"decision": "approve", "user_id": "u1"}},
    )
    response_part2.function_response.id = interrupt_id2

    events3 = await _run_runner(
        runner,
        "test_session",
        response_part2,
        invocation_id=last_event2.invocation_id,
    )

    final_event = events3[-1]
    result = final_event.output
    assert result["outcome"] == HITLOutcome.APPROVED.value
    assert result["edit_rounds"] == 1
    assert result["action"]["quantity"] == 10


@pytest.mark.asyncio
async def test_gate_edit_invalid_field_rejects(
    sample_proposed_action, mock_firestore_client
):
    workflow = _create_gate_workflow()
    runner = Runner(
        agent=workflow,
        app_name="test_app",
        session_service=InMemorySessionService(),
        auto_create_session=True,
    )

    events1 = await _run_runner(
        runner,
        "test_session",
        {"action": sample_proposed_action.model_dump()},
    )
    last_event1 = events1[-1]
    interrupt_id1, _ = _get_request_input_interrupt(last_event1)

    response_part = Part.from_function_response(
        name="adk_request_input",
        response={"interruptId": interrupt_id1, "payload": {"decision": "edit", "changes": {"action_id": "hacked"}, "user_id": "u1"}},
    )
    response_part.function_response.id = interrupt_id1

    events2 = await _run_runner(
        runner,
        "test_session",
        response_part,
        invocation_id=last_event1.invocation_id,
    )

    final_event = events2[-1]
    result = final_event.output
    assert result["outcome"] == HITLOutcome.REJECTED.value
    assert "invalid_edit" in result["reason"]
    assert "action_id" in result["reason"]
    mock_firestore_client.update_proposed_action_status.assert_called_once_with(
        "act-test-123", ActionStatus.REJECTED
    )


@pytest.mark.asyncio
async def test_gate_hits_edit_limit_auto_rejects(
    sample_proposed_action, mock_firestore_client
):
    workflow = _create_gate_workflow()
    runner = Runner(
        agent=workflow,
        app_name="test_app",
        session_service=InMemorySessionService(),
        auto_create_session=True,
    )

    events = await _run_runner(
        runner,
        "test_session",
        {"action": sample_proposed_action.model_dump()},
    )

    last_event = events[-1]
    interrupt_id, _ = _get_request_input_interrupt(last_event)

    # Perform 3 edit rounds (quantities 10, 20, 30)
    for q in [10, 20, 30]:
        response_part = Part.from_function_response(
            name="adk_request_input",
            response={"interruptId": interrupt_id, "payload": {"decision": "edit", "changes": {"quantity": q}, "user_id": "u1"}},
        )
        response_part.function_response.id = interrupt_id

        events = await _run_runner(
            runner,
            "test_session",
            response_part,
            invocation_id=last_event.invocation_id,
        )
        last_event = events[-1]
        interrupt_id, _ = _get_request_input_interrupt(last_event)

    result = last_event.output
    assert result["outcome"] == HITLOutcome.REJECTED.value
    assert result["reason"] == "edit_limit_exceeded"
    assert result["edit_rounds"] == 3


@pytest.mark.asyncio
async def test_gate_missing_action_raises(mock_firestore_client):
    workflow = _create_gate_workflow()
    runner = Runner(
        agent=workflow,
        app_name="test_app",
        session_service=InMemorySessionService(),
        auto_create_session=True,
    )

    with pytest.raises(ValueError, match="hitl_approval_gate requires 'action'"):
        await _run_runner(
            runner,
            "test_session",
            {},
        )


@pytest.mark.asyncio
async def test_gate_malformed_response_raises(
    sample_proposed_action, mock_firestore_client
):
    workflow = _create_gate_workflow()
    runner = Runner(
        agent=workflow,
        app_name="test_app",
        session_service=InMemorySessionService(),
        auto_create_session=True,
    )

    events1 = await _run_runner(
        runner,
        "test_session",
        {"action": sample_proposed_action.model_dump()},
    )
    last_event1 = events1[-1]
    interrupt_id1, _ = _get_request_input_interrupt(last_event1)

    response_part = Part.from_function_response(
        name="adk_request_input",
        response={"interruptId": interrupt_id1, "payload": "just a string"},
    )
    response_part.function_response.id = interrupt_id1

    with pytest.raises(ValueError, match="HITL response must be a dict"):
        await _run_runner(
            runner,
            "test_session",
            response_part,
            invocation_id=last_event1.invocation_id,
        )


@pytest.mark.asyncio
async def test_gate_unknown_decision_raises(
    sample_proposed_action, mock_firestore_client
):
    workflow = _create_gate_workflow()
    runner = Runner(
        agent=workflow,
        app_name="test_app",
        session_service=InMemorySessionService(),
        auto_create_session=True,
    )

    events1 = await _run_runner(
        runner,
        "test_session",
        {"action": sample_proposed_action.model_dump()},
    )
    last_event1 = events1[-1]
    interrupt_id1, _ = _get_request_input_interrupt(last_event1)

    response_part = Part.from_function_response(
        name="adk_request_input",
        response={"interruptId": interrupt_id1, "payload": {"decision": "maybe", "user_id": "u1"}},
    )
    response_part.function_response.id = interrupt_id1

    with pytest.raises(ValueError, match="Unknown decision 'maybe'"):
        await _run_runner(
            runner,
            "test_session",
            response_part,
            invocation_id=last_event1.invocation_id,
        )


@pytest.mark.asyncio
async def test_gate_works_without_reviewer_verdict(
    sample_proposed_action, mock_firestore_client
):
    workflow = _create_gate_workflow()
    runner = Runner(
        agent=workflow,
        app_name="test_app",
        session_service=InMemorySessionService(),
        auto_create_session=True,
    )

    events1 = await _run_runner(
        runner,
        "test_session",
        {"action": sample_proposed_action.model_dump(), "reviewer_verdict": None},
    )
    last_event1 = events1[-1]
    interrupt_id1, args1 = _get_request_input_interrupt(last_event1)
    payload1 = args1.get("message")
    assert payload1["reviewer_verdict"] is None

    response_part = Part.from_function_response(
        name="adk_request_input",
        response={"interruptId": interrupt_id1, "payload": {"decision": "approve", "user_id": "u1"}},
    )
    response_part.function_response.id = interrupt_id1

    events2 = await _run_runner(
        runner,
        "test_session",
        response_part,
        invocation_id=last_event1.invocation_id,
    )

    final_event = events2[-1]
    result = final_event.output
    assert result["outcome"] == HITLOutcome.APPROVED.value
