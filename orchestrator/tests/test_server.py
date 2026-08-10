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


def test_sse_logs_exception_with_traceback(caplog):
    """The SSE error frame goes to the client, but the server MUST log the full
    exception so operators can trace failures (e.g. Agent Registry 401s) in
    Cloud Logging — otherwise the wire error is the only record and it lands
    only in the browser."""
    import asyncio
    import logging

    from src.orchestrator.server import _sse

    async def failing():
        raise RuntimeError("registry 401: unauthorized")
        yield  # pragma: no cover

    async def drain():
        async for _ in _sse(failing()):
            pass

    with caplog.at_level(logging.ERROR, logger="orchestrator.server"):
        asyncio.run(drain())

    matching = [r for r in caplog.records if "SSE event stream raised" in r.getMessage()]
    assert matching, f"expected SSE-raise log record, got {[r.getMessage() for r in caplog.records]}"
    record = matching[0]
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None, "logger.exception must attach exc_info for tracebacks"


def test_stream_json_lines_logs_exception_with_traceback(caplog):
    """Same guarantee as _sse but for the Agent Runtime streamQuery NDJSON path."""
    import asyncio
    import logging

    from src.orchestrator.server import _stream_json_lines

    async def failing():
        raise RuntimeError("agent runtime blew up")
        yield  # pragma: no cover

    async def drain():
        async for _ in _stream_json_lines(failing()):
            pass

    with caplog.at_level(logging.ERROR, logger="orchestrator.server"):
        asyncio.run(drain())

    matching = [r for r in caplog.records if "NDJSON event stream raised" in r.getMessage()]
    assert matching
    assert matching[0].exc_info is not None


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


def test_onboarding_apply_persists_via_writer(client_with_runner):
    """POST /v1/onboarding/apply must call write_ips_from_interview_result and
    return the actual ips_id + version rather than fabricating success."""
    from src.orchestrator.contracts.ips import (
        InvestmentPolicyStatement,
        IPSStatus,
        RiskTolerance,
    )
    from src.orchestrator.contracts.liabilities import LiabilitiesSnapshot

    client, _, _ = client_with_runner

    fake_ips = InvestmentPolicyStatement(
        ips_id="ips-wiz-1",
        user_id="u_wiz",
        version=1,
        status=IPSStatus.ACTIVE,
        effective_date="2026-01-01",
        risk_tolerance=RiskTolerance.MODERATE,
        time_horizon_years=10,
        target_allocation=[],
        constraints=__import__(
            "src.orchestrator.contracts.ips", fromlist=["Constraints"]
        ).Constraints(concentration_limit_percent=10.0),
        created_at=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ),
    )
    fake_liab = LiabilitiesSnapshot(
        user_id="u_wiz",
        as_of=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ),
        liabilities=[],
    )

    with patch(
        "src.orchestrator.server.write_ips_from_interview_result",
        return_value=(fake_ips, fake_liab),
    ) as mock_writer:
        r = client.post(
            "/v1/onboarding/apply",
            json={
                "result": {
                    "user_id": "u_wiz",
                    "risk_tolerance": "moderate",
                    "time_horizon_years": 10,
                    "target_allocation": [],
                    "identified_liabilities": [],
                    "additional_goals": [],
                    "interview_summary": "wizard",
                },
                "trigger": "initial",
                "approval_required_above_usd": 5000,
                "approval_required_above_percent": 5,
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body == {
            "status": "applied",
            "ips_id": "ips-wiz-1",
            "version": 1,
            "liabilities_count": 0,
        }
        # Thresholds must be threaded through to the writer.
        _, kwargs = mock_writer.call_args
        assert kwargs["approval_required_above_usd"] == 5000
        assert kwargs["approval_required_above_percent"] == 5
        assert kwargs["trigger"] == "initial"


def test_onboarding_apply_returns_500_on_writer_failure(client_with_runner):
    """UI must not be able to fabricate success — a writer failure has to surface."""
    client, _, _ = client_with_runner

    with patch(
        "src.orchestrator.server.write_ips_from_interview_result",
        side_effect=RuntimeError("firestore down"),
    ):
        r = client.post(
            "/v1/onboarding/apply",
            json={
                "result": {
                    "user_id": "u_wiz",
                    "risk_tolerance": "moderate",
                    "time_horizon_years": 10,
                    "target_allocation": [],
                    "identified_liabilities": [],
                    "additional_goals": [],
                    "interview_summary": "wizard",
                }
            },
        )
        assert r.status_code == 500
        assert "apply_failed" in r.json()["detail"]

