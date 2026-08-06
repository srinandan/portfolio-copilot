"""HTTP entrypoint for the orchestrator container on Vertex AI Agent Runtime.

Agent Runtime custom containers must serve HTTP on `$PORT` (defaults to 8080)
and expose `/livez` + `/readyz` probes; requests are proxied through to the
container by the Agent Engine control plane. This module builds a minimal
FastAPI app around the existing ADK `root_agent` Workflow so the same planner
that runs in tests is what the container serves.

Endpoints:
  GET  /livez             — always 200 once the process is up.
  GET  /readyz            — 200 after startup verification (SKILL.md metadata
                            + required secrets) has succeeded.
  POST /v1/invoke         — start a planning turn. Body: {"user_id", "message",
                            "session_id"?}. Streams ADK Runner events back
                            as Server-Sent Events (Content-Type: text/event-stream);
                            each `data:` line is a JSON-serialized ADK Event.
  POST /v1/resume         — resume a paused session (HITL). Body: {"user_id",
                            "session_id", "invocation_id", "interrupt_id",
                            "payload"}. Same SSE response format.

The response format is a lightweight SSE — the gateway (Go) proxies these
events straight through to the frontend, so the SSE shape is the wire
contract with the frontend.
"""

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from google.adk.runners import Runner
from google.genai.types import Part, UserContent
from pydantic import BaseModel

from .planner import root_agent
from .session_manager import SessionManager

logger = logging.getLogger(__name__)

APP_NAME = os.environ.get("ORCHESTRATOR_APP_NAME", "portfolio_copilot")


class InvokeRequest(BaseModel):
    user_id: str
    message: str
    session_id: Optional[str] = None


class ResumeRequest(BaseModel):
    user_id: str
    session_id: str
    invocation_id: str
    interrupt_id: str
    payload: Any


class ServerState:
    session_manager: Optional[SessionManager] = None
    runner: Optional[Runner] = None
    ready: bool = False


state = ServerState()


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # importing planner already ran verify_all_skills_metadata + verify_required_secrets
    # at module import time (see planner.py); if either failed the process wouldn't have
    # reached here. Wire the Runner now so requests find it ready.
    state.session_manager = SessionManager()
    state.runner = Runner(
        app_name=APP_NAME,
        agent=root_agent,
        session_service=state.session_manager.session_service,
        memory_service=state.session_manager.memory_service,
        auto_create_session=True,
    )
    state.ready = True
    logger.info("Orchestrator HTTP server ready (app_name=%s)", APP_NAME)
    yield
    state.ready = False


app = FastAPI(title="Portfolio Copilot Orchestrator", version="0.1.0", lifespan=_lifespan)


@app.get("/livez")
async def livez() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    if not state.ready or state.runner is None:
        raise HTTPException(status_code=503, detail="not ready")
    return {"status": "ok"}


def _event_to_wire(event: Any) -> dict[str, Any]:
    """Serialize an ADK Event to a JSON-safe wire dict for SSE.

    ADK Events are Pydantic models; use model_dump when available, else fall back
    to str(). The gateway proxies these opaquely — the frontend understands the
    shape.
    """
    if hasattr(event, "model_dump"):
        try:
            return event.model_dump(mode="json")
        except Exception:
            pass
    return {"raw": str(event)}


async def _sse(events: AsyncIterator[Any]) -> AsyncIterator[bytes]:
    try:
        async for event in events:
            payload = json.dumps(_event_to_wire(event), default=str)
            yield f"data: {payload}\n\n".encode("utf-8")
    except Exception as e:
        err = json.dumps({"error": str(e)})
        yield f"event: error\ndata: {err}\n\n".encode("utf-8")


async def _stream_json_lines(events: AsyncIterator[Any]) -> AsyncIterator[bytes]:
    try:
        async for event in events:
            payload = json.dumps(_event_to_wire(event), default=str)
            yield f"{payload}\n".encode("utf-8")
    except Exception as e:
        err = json.dumps({"error": str(e)})
        yield f"{err}\n".encode("utf-8")


@app.post("/api/stream_reasoning_engine")
async def stream_reasoning_engine(request: Request) -> StreamingResponse:
    """Agent Runtime (Reasoning Engine :streamQuery) endpoint."""
    if state.runner is None:
        raise HTTPException(status_code=503, detail="runner not initialized")

    body = await request.json()
    class_method = body.get("class_method", "invoke")
    input_data = body.get("input", body)
    if not isinstance(input_data, dict):
        input_data = {}

    user_id = input_data.get("user_id", "usr_default")
    session_id = input_data.get("session_id")
    message = input_data.get("message", "")

    if class_method in ("resume", "stream_query_resume") or "interrupt_id" in input_data:
        interrupt_id = input_data.get("interrupt_id", "")
        invocation_id = input_data.get("invocation_id", "")
        payload = input_data.get("payload", {})
        response_part = Part.from_function_response(
            name="adk_request_input",
            response={"interruptId": interrupt_id, "payload": payload},
        )
        if response_part.function_response is not None:
            response_part.function_response.id = interrupt_id

        events = state.runner.run_async(
            user_id=user_id,
            session_id=session_id,
            invocation_id=invocation_id,
            new_message=UserContent(parts=[response_part]),
        )
    else:
        session = await state.session_manager.get_or_create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )
        events = state.runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=UserContent(parts=[Part.from_text(text=message)]),
        )

    return StreamingResponse(_stream_json_lines(events), media_type="application/x-ndjson")


@app.post("/api/reasoning_engine")
async def reasoning_engine(request: Request) -> dict[str, Any]:
    """Agent Runtime (Reasoning Engine :query) non-streaming endpoint."""
    if state.runner is None:
        raise HTTPException(status_code=503, detail="runner not initialized")

    body = await request.json()
    input_data = body.get("input", body)
    if not isinstance(input_data, dict):
        input_data = {}

    user_id = input_data.get("user_id", "usr_default")
    session_id = input_data.get("session_id")
    message = input_data.get("message", "")

    session = await state.session_manager.get_or_create_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    events = state.runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=UserContent(parts=[Part.from_text(text=message)]),
    )

    collected = []
    async for event in events:
        collected.append(_event_to_wire(event))
    return {"events": collected}


@app.post("/v1/invoke")
async def invoke(req: InvokeRequest) -> StreamingResponse:
    if state.runner is None:
        raise HTTPException(status_code=503, detail="runner not initialized")

    session = await state.session_manager.get_or_create_session(
        app_name=APP_NAME, user_id=req.user_id, session_id=req.session_id
    )
    events = state.runner.run_async(
        user_id=req.user_id,
        session_id=session.id,
        new_message=UserContent(parts=[Part.from_text(text=req.message)]),
    )
    return StreamingResponse(_sse(events), media_type="text/event-stream")


@app.post("/v1/resume")
async def resume(req: ResumeRequest) -> StreamingResponse:
    if state.runner is None:
        raise HTTPException(status_code=503, detail="runner not initialized")

    response_part = Part.from_function_response(
        name="adk_request_input",
        response={"interruptId": req.interrupt_id, "payload": req.payload},
    )
    # ADK expects the function-response part's id to match the interrupt id.
    if response_part.function_response is not None:
        response_part.function_response.id = req.interrupt_id

    events = state.runner.run_async(
        user_id=req.user_id,
        session_id=req.session_id,
        invocation_id=req.invocation_id,
        new_message=UserContent(parts=[response_part]),
    )
    return StreamingResponse(_sse(events), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
