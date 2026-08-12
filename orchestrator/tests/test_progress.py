"""Tests for the streaming progress channel (orchestrator.progress) and its
interleaving into the SSE/NDJSON stream (server._interleave_progress).

The end-to-end test drives the real planner through the real interleave path,
which is what proves the whole feature works: report_progress() calls made deep
inside the planner (including inside asyncio.gather sub-tasks) must reach the
wire stream via the context-variable channel.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.workflow import Workflow
from google.genai.types import Part, UserContent

from src.orchestrator.planner import root_planner
from src.orchestrator.progress import (
    PROGRESS_CHANNEL,
    report_progress,
    report_skill_progress,
    stage_label,
)
from src.orchestrator.registry_client import Skill
from src.orchestrator.server import _interleave_progress


def test_report_progress_is_noop_without_channel():
    """No channel installed (non-streaming paths, unit tests) => silent no-op,
    never raises."""
    assert PROGRESS_CHANNEL.get() is None
    report_progress("discovery", "running", "Discovering authorized skills")  # must not raise


@pytest.mark.asyncio
async def test_report_progress_puts_structured_event():
    queue: asyncio.Queue = asyncio.Queue()
    token = PROGRESS_CHANNEL.set(queue)
    try:
        report_progress("portfolio-analysis", "running", "Analyzing portfolio drift", detail="8% over target")
    finally:
        PROGRESS_CHANNEL.reset(token)

    event = queue.get_nowait()
    assert event == {
        "kind": "progress",
        "stage": "portfolio-analysis",
        "status": "running",
        "label": "Analyzing portfolio drift",
        "detail": "8% over target",
    }


@pytest.mark.asyncio
async def test_report_skill_progress_derives_stage_and_label():
    queue: asyncio.Queue = asyncio.Queue()
    token = PROGRESS_CHANNEL.set(queue)
    try:
        # Accepts the private- prefix and the full resource name form.
        report_skill_progress("private-spending-analysis", "done")
    finally:
        PROGRESS_CHANNEL.reset(token)

    event = queue.get_nowait()
    assert event["stage"] == "spending-analysis"
    assert event["status"] == "done"
    assert event["label"] == "Analyzing spending"


def test_stage_label_prettifies_unknown_stage():
    assert stage_label("discovery") == "Discovering authorized skills"
    assert stage_label("some-new-stage") == "Some new stage"


class _FakeEvent:
    """Stands in for an ADK Event: _event_to_wire calls model_dump(mode=...)."""

    def __init__(self, n: int):
        self._n = n

    def model_dump(self, mode: str = "python"):
        return {"kind": "adk_event", "n": self._n}


@pytest.mark.asyncio
async def test_interleave_merges_progress_with_runner_events():
    """The core mechanism: report_progress() called from inside the drained
    event stream (i.e. from the same context the runner runs in) is interleaved
    onto the output stream in arrival order. This exercises context-variable
    propagation across the create_task boundary inside _interleave_progress."""

    async def fake_events():
        report_progress("discovery", "running", "Discovering authorized skills")
        yield _FakeEvent(1)
        report_progress("discovery", "done", "Discovering authorized skills")
        yield _FakeEvent(2)

    items = [item async for item in _interleave_progress(fake_events())]

    progress = [i for i in items if i.get("kind") == "progress"]
    adk = [i for i in items if i.get("kind") == "adk_event"]

    assert [(p["stage"], p["status"]) for p in progress] == [
        ("discovery", "running"),
        ("discovery", "done"),
    ]
    assert [a["n"] for a in adk] == [1, 2]
    # Interleaved in real arrival order: running, event1, done, event2.
    assert [i.get("status") or i.get("n") for i in items] == ["running", 1, "done", 2]
    # Channel is torn down after the stream completes.
    assert PROGRESS_CHANNEL.get() is None


@pytest.mark.asyncio
async def test_interleave_forwards_stream_error_marker():
    async def failing():
        raise RuntimeError("registry 401")
        yield  # pragma: no cover

    items = [item async for item in _interleave_progress(failing())]
    assert len(items) == 1
    assert items[0]["__stream_error__"]["error"] == "registry 401"
    assert items[0]["__stream_error__"]["type"] == "RuntimeError"


@pytest.mark.asyncio
async def test_root_planner_emits_stage_progress_through_interleave():
    """End-to-end: run the real planner (spending-analysis authorized, dispatch
    mocked) through the real interleave path and assert the discovery and skill
    stage transitions land on the wire stream as progress events."""
    agent = Workflow(name="test_root_progress", edges=[("START", root_planner)])
    runner = Runner(
        app_name="test_app",
        agent=agent,
        session_service=InMemorySessionService(),
        memory_service=InMemoryMemoryService(),
        auto_create_session=True,
    )

    with (
        patch(
            "src.orchestrator.planner.AgentRegistryClient.list_authorized_skills", new_callable=AsyncMock
        ) as mock_list,
        patch("src.orchestrator.planner.emit_skill_invoked_audit"),
        patch("src.orchestrator.planner.dispatch_managed_skill", new_callable=AsyncMock) as mock_dispatch,
        patch("src.orchestrator.planner.preload_spending_facts") as mock_preload,
    ):
        mock_list.return_value = [
            Skill(
                name="projects/p/locations/global/skills/private-spending-analysis",
                target_state="TARGET_STATE_ACTIVE",
                default_revision="rev-spend-1",
            ),
        ]
        mock_preload.return_value = {}
        mock_dispatch.return_value = {"narrative_summary": "Spending within norms."}

        stream = runner.run_async(
            user_id="user_progress",
            session_id="sess_progress",
            new_message=UserContent(parts=[Part.from_text(text='{"user_id": "user_progress"}')]),
        )
        items = [item async for item in _interleave_progress(stream)]

    progress_by_stage = {}
    for i in items:
        if i.get("kind") == "progress":
            progress_by_stage.setdefault(i["stage"], []).append(i["status"])

    assert progress_by_stage.get("discovery") == ["running", "done"]
    assert progress_by_stage.get("spending-analysis") == ["running", "done"]
    # The final ADK output event (the planner's results list) is still on the stream.
    assert any(i.get("kind") != "progress" for i in items)
