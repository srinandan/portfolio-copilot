"""Smoke tests for the orchestrator HTTP server.

Verifies the shape of the FastAPI app that runs inside the Agent Runtime
container: liveness/readiness probes respond, and /v1/invoke streams SSE
events from a mocked Runner.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_with_runner():
    """TestClient wired to a mocked Runner so invoke returns a canned event stream.

    The FastAPI startup handler builds a real Runner; we override it after the
    lifespan has run so the request path picks up the fake.
    """
    from src.orchestrator import server

    fake_event = MagicMock()
    fake_event.model_dump.return_value = {"kind": "test_event", "output": "hello"}

    async def _fake_run_async(**_kwargs):
        yield fake_event

    fake_runner = MagicMock()
    fake_runner.run_async = _fake_run_async

    fake_sm = MagicMock()
    fake_session = MagicMock()
    fake_session.id = "sess_abc"
    fake_sm.get_or_create_session = AsyncMock(return_value=fake_session)

    with patch("src.orchestrator.server.SessionManager", return_value=fake_sm), \
         patch("src.orchestrator.server.Runner", return_value=fake_runner):
        with TestClient(server.app) as client:
            # Startup handler has run and installed the mocked SessionManager + Runner
            # via the patch above. Force ready in case another test left it False.
            server.state.ready = True
            yield client, fake_runner, fake_sm


def test_livez_always_ok():
    from src.orchestrator import server

    with TestClient(server.app) as client:
        r = client.get("/livez")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


def test_lifespan_runs_startup_verifications():
    from src.orchestrator import server

    with patch("src.orchestrator.skills._skill_metadata.verify_all_skills_metadata") as mock_verify_skills, \
         patch("src.orchestrator.managed_agents.secret_loader.verify_required_secrets") as mock_verify_secrets, \
         patch("src.orchestrator.server.SessionManager"), \
         patch("src.orchestrator.server.Runner"):
        with TestClient(server.app):
            mock_verify_skills.assert_called_once()
            mock_verify_secrets.assert_called_once()


def test_readyz_503_before_startup_completes():
    from src.orchestrator import server

    # Force the not-ready state; startup handler in TestClient's lifespan flips it back on entry,
    # so we override after entering the context.
    with TestClient(server.app) as client:
        server.state.runner = None
        server.state.ready = False
        r = client.get("/readyz")
        assert r.status_code == 503


def test_invoke_returns_sse_stream(client_with_runner):
    client, fake_runner, fake_sm = client_with_runner
    with client.stream(
        "POST",
        "/v1/invoke",
        json={"user_id": "u1", "message": "start"},
    ) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        body = b"".join(r.iter_bytes()).decode("utf-8")

    assert body.startswith("data: ")
    payload = json.loads(body[len("data: ") :].strip())
    assert payload == {"kind": "test_event", "output": "hello"}
    fake_sm.get_or_create_session.assert_awaited_once()


def test_resume_returns_sse_stream(client_with_runner):
    client, fake_runner, _ = client_with_runner
    with client.stream(
        "POST",
        "/v1/resume",
        json={
            "user_id": "u1",
            "session_id": "sess_abc",
            "invocation_id": "inv_1",
            "interrupt_id": "int_1",
            "payload": {"decision": "approve"},
        },
    ) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")


def test_invoke_503_when_runner_not_initialized():
    from src.orchestrator import server

    with TestClient(server.app) as client:
        server.state.runner = None
        r = client.post("/v1/invoke", json={"user_id": "u1", "message": "hi"})
        assert r.status_code == 503


def test_sse_serializes_error_events():
    """When the underlying event stream raises, the SSE stream emits an `error` event
    instead of crashing the connection."""
    import asyncio

    from src.orchestrator.server import _sse

    async def failing():
        raise RuntimeError("boom")
        yield  # pragma: no cover — never reached

    async def collect():
        return b"".join([chunk async for chunk in _sse(failing())]).decode("utf-8")

    out = asyncio.run(collect())
    assert "event: error" in out
    assert "boom" in out


def test_stream_reasoning_engine_invoke(client_with_runner):
    client, fake_runner, fake_sm = client_with_runner
    with client.stream(
        "POST",
        "/api/stream_reasoning_engine",
        json={"class_method": "invoke", "input": {"user_id": "u1", "message": "hello"}},
    ) as r:
        assert r.status_code == 200
        assert "application/x-ndjson" in r.headers["content-type"]
        body = b"".join(r.iter_bytes()).decode("utf-8").strip()

    payload = json.loads(body)
    assert payload == {"kind": "test_event", "output": "hello"}
    fake_sm.get_or_create_session.assert_awaited_once()


def test_stream_reasoning_engine_resume(client_with_runner):
    client, fake_runner, _ = client_with_runner
    with client.stream(
        "POST",
        "/api/stream_reasoning_engine",
        json={
            "class_method": "resume",
            "input": {
                "user_id": "u1",
                "session_id": "sess_abc",
                "invocation_id": "inv_1",
                "interrupt_id": "int_1",
                "payload": {"decision": "approve"},
            },
        },
    ) as r:
        assert r.status_code == 200
        body = b"".join(r.iter_bytes()).decode("utf-8").strip()

    payload = json.loads(body)
    assert payload == {"kind": "test_event", "output": "hello"}


def test_reasoning_engine_query(client_with_runner):
    client, fake_runner, _ = client_with_runner
    r = client.post(
        "/api/reasoning_engine",
        json={"input": {"user_id": "u1", "message": "hello"}},
    )
    assert r.status_code == 200
    assert r.json() == {"events": [{"kind": "test_event", "output": "hello"}]}

