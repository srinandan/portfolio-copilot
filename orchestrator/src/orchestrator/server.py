"""HTTP entrypoint for the orchestrator container on Agent Platform Agent Runtime.

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

Alongside the ADK Event frames, the stream also carries advisory *progress*
frames — `data:` lines whose JSON has `{"kind": "progress", ...}` — reported by
the planner as each pipeline stage runs, so the UI can show live progress during
the 2-4 minute analysis. See `progress.py`, `_interleave_progress` below, and
ADR-0018. Progress frames are advisory UI signals only; the authoritative record
of what ran is the Firestore audit log.
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from google.adk.runners import Runner
from google.genai.types import Part, UserContent
from pydantic import BaseModel

from .contracts.goals_onboarding import GoalsOnboardingResult
from .logger import get_logger
from .planner import root_agent
from .progress import PROGRESS_CHANNEL
from .session_manager import SessionManager
from .state import write_ips_from_interview_result

logger = get_logger(__name__)

APP_NAME = os.environ.get("AGENT_ENGINE_ID") or os.environ.get("ORCHESTRATOR_APP_NAME", "portfolio_copilot")


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


class ApplyOnboardingRequest(BaseModel):
    """Structured wizard submission bypassing the LLM interview.

    The frontend wizard collects clean typed data; there's no need for an LLM
    to re-parse a prose serialization of it. This body is validated as a
    GoalsOnboardingResult plus optional approval thresholds and written
    directly by the same writer the LLM path uses, so the IPS_CREATED audit
    entry is identical either way.
    """

    result: GoalsOnboardingResult
    trigger: str = "initial"
    approval_required_above_usd: Optional[float] = None
    approval_required_above_percent: Optional[float] = None


class ServerState:
    session_manager: Optional[SessionManager] = None
    runner: Optional[Runner] = None
    ready: bool = False


state = ServerState()


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # Startup verification of SKILL.md metadata reachability and required secrets
    from .managed_agents.secret_loader import verify_required_secrets
    from .skills._skill_metadata import verify_all_skills_metadata

    verify_all_skills_metadata()
    verify_required_secrets()

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


def _resolve_project_id() -> str:
    """Resolves the GCP project ID string for span export.

    Cloud Trace requires an alphanumeric Project ID (e.g. 'my-project') and
    rejects numeric Project Numbers (e.g. '432423772502') with:
        400 Invalid project id in name!

    In Agent Runtime containers, GOOGLE_CLOUD_PROJECT is often automatically
    populated with the numeric project number, while PROJECT_ID carries the
    user-configured string ID. We prefer non-numeric string IDs.
    """
    candidates = []
    for key in (
        "OTEL_EXPORTER_GCP_TRACE_PROJECT_ID",
        "PROJECT_ID",
        "FIRESTORE_PROJECT_ID",
        "GOOGLE_CLOUD_PROJECT",
    ):
        value = os.environ.get(key)
        if value:
            candidates.append(value)

    # Prefer non-numeric project ID strings over numeric project numbers
    for c in candidates:
        if not c.isdigit():
            return c
    return candidates[0] if candidates else ""


def _service_name() -> str:
    """The OpenTelemetry ``service.name`` the orchestrator's spans group under in Cloud Trace."""
    return os.environ.get("OTEL_SERVICE_NAME") or "portfolio-copilot-orchestrator"


def _build_tracer_provider(service_name: str, exporter):
    """Builds a TracerProvider carrying a ``service.name`` resource and exporting via
    ``exporter`` (batched). Pure — no global side effects — so it is unit-testable."""
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider


def _configure_span_export() -> None:
    """Ensures the orchestrator's own spans are exported to Cloud Trace.

    Ingress instrumentation alone (extracting ``traceparent`` and opening a server
    span) does not *emit* anything — it needs a TracerProvider with an exporter.
    Nothing in this process configured one for these SDK spans, so the
    orchestrator emitted no traces (only the frontend did). This wires a Cloud
    Trace exporter, with a ``service.name`` resource so the spans are attributable,
    so the server span and the ADK/GenAI spans nesting under it actually reach
    Cloud Trace.

    If a real SDK TracerProvider already exists (e.g. one Agent Runtime installed),
    the Cloud Trace exporter is attached to it; otherwise a new provider carrying
    our ``service.name`` is installed. Skips silently when no project is resolvable
    (local/tests) — trace-context propagation still works.
    """
    project_id = _resolve_project_id()
    if not project_id:
        logger.info("No GCP project resolvable; orchestrator span export disabled (propagation still active)")
        return
    try:
        from opentelemetry import trace as ot_trace
        from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        exporter = CloudTraceSpanExporter(project_id=project_id)
        current = ot_trace.get_tracer_provider()
        if isinstance(current, TracerProvider):
            current.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("Attached Cloud Trace exporter to existing TracerProvider (project=%s)", project_id)
        else:
            ot_trace.set_tracer_provider(_build_tracer_provider(_service_name(), exporter))
            logger.info(
                "Installed orchestrator TracerProvider with Cloud Trace exporter (service=%s, project=%s)",
                _service_name(),
                project_id,
            )
    except Exception:
        logger.exception("Cloud Trace exporter setup failed; orchestrator span export disabled")


def _init_server_tracing(fastapi_app: FastAPI) -> None:
    """Instrument the FastAPI ingress AND export the orchestrator's spans to Cloud Trace.

    Two pieces are needed for the orchestrator to participate in the end-to-end
    trace (ADR-0019):

    1. **Context extraction (ingress).** The Go gateway injects a W3C
       ``traceparent``; FastAPI instrumentation extracts it, opens a **server
       span** as its child, and activates that context so the ADK/GenAI spans
       created while handling the request nest under it — one Trace ID from
       browser click to agent execution.
    2. **Span export.** Extraction alone emits nothing. Agent Runtime's
       ``GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY`` did not install an exporting
       provider for these SDK spans in-process, so ``_configure_span_export``
       wires a Cloud Trace exporter with a ``service.name`` resource.

    Opt-out via ``OTEL_TRACES_ENABLED=false``; never fatal — a telemetry failure
    must not stop the server from serving.

    Note: in Agent Engine (Vertex ``:streamQuery``) deployments, whether the
    inbound ``traceparent`` reaches this container is subject to Vertex header
    forwarding; in direct (``ORCHESTRATOR_URL``) mode it always does. Either way,
    the orchestrator now emits its own spans.
    """
    if os.environ.get("OTEL_TRACES_ENABLED", "").lower() in ("false", "0"):
        logger.info("FastAPI server-side tracing disabled via OTEL_TRACES_ENABLED")
        return
    try:
        from opentelemetry import propagate
        from opentelemetry.baggage.propagation import W3CBaggagePropagator
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.propagators.composite import CompositePropagator
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

        # W3C TraceContext is OTel's default; set it explicitly so ingress
        # extraction is robust regardless of any runtime propagator override.
        propagate.set_global_textmap(CompositePropagator([TraceContextTextMapPropagator(), W3CBaggagePropagator()]))
        # Wire the exporter BEFORE instrumenting so the server span is exported.
        _configure_span_export()
        FastAPIInstrumentor.instrument_app(fastapi_app)
        logger.info("FastAPI server-side tracing enabled (W3C extraction + Cloud Trace export)")
    except Exception:
        logger.exception("FastAPI tracing init failed; continuing without ingress spans")


app = FastAPI(title="Portfolio Copilot Orchestrator", version="0.1.0", lifespan=_lifespan)
_init_server_tracing(app)


@app.exception_handler(Exception)
async def _log_unhandled(request: Request, exc: Exception) -> JSONResponse:
    """Ensure every unhandled exception hits Cloud Logging with a traceback.

    FastAPI's default handler returns a generic 500 without logging — that's
    how we've been losing 401s and other upstream failures. Preserve
    HTTPException semantics by re-raising the response for those.
    """
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "internal_server_error"})


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


# Sentinel signalling the runner event stream has been fully drained.
_STREAM_DONE = object()
# Marker key wrapping a stream failure so the framing layer can emit an error frame.
_STREAM_ERROR_KEY = "__stream_error__"


async def _interleave_progress(events: AsyncIterator[Any]) -> AsyncIterator[Dict[str, Any]]:
    """Yields wire dicts for both ADK Runner events and out-of-band progress events.

    A per-run ``asyncio.Queue`` is installed on ``PROGRESS_CHANNEL`` for the
    lifetime of the stream, so the planner's ``report_progress`` calls land here
    and interleave with the ADK event stream in real arrival order. The context
    variable is set *before* the drain task is created so the copied task
    context (and any ``asyncio.gather`` sub-tasks the planner spawns) can see the
    queue.

    Progress dicts carry ``{"kind": "progress"}``; ADK events are serialized via
    :func:`_event_to_wire`. A stream failure is surfaced as a dict keyed by
    ``_STREAM_ERROR_KEY`` so the framing layer can emit the SSE ``error`` frame
    the frontend expects (behavior preserved from the previous implementation).
    """
    queue: "asyncio.Queue[Any]" = asyncio.Queue()
    token = PROGRESS_CHANNEL.set(queue)

    async def _drain_runner() -> None:
        try:
            async for event in events:
                queue.put_nowait(_event_to_wire(event))
        except Exception as e:
            # Logged here (with traceback) for operators; forwarded to the client
            # as an error frame by the framing layer below.
            logger.exception("event stream raised; forwarding error frame to client")
            queue.put_nowait({_STREAM_ERROR_KEY: {"error": str(e), "type": type(e).__name__}})
        finally:
            queue.put_nowait(_STREAM_DONE)

    task = asyncio.create_task(_drain_runner())
    try:
        while True:
            item = await queue.get()
            if item is _STREAM_DONE:
                break
            yield item
    finally:
        PROGRESS_CHANNEL.reset(token)
        if not task.done():
            task.cancel()


async def _sse(events: AsyncIterator[Any]) -> AsyncIterator[bytes]:
    async for item in _interleave_progress(events):
        if _STREAM_ERROR_KEY in item:
            err = json.dumps(item[_STREAM_ERROR_KEY], default=str)
            yield f"event: error\ndata: {err}\n\n".encode("utf-8")
            continue
        payload = json.dumps(item, default=str)
        yield f"data: {payload}\n\n".encode("utf-8")


async def _stream_json_lines(events: AsyncIterator[Any]) -> AsyncIterator[bytes]:
    async for item in _interleave_progress(events):
        if _STREAM_ERROR_KEY in item:
            err = json.dumps(item[_STREAM_ERROR_KEY], default=str)
            yield f"{err}\n".encode("utf-8")
            continue
        payload = json.dumps(item, default=str)
        yield f"{payload}\n".encode("utf-8")


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

    user_id = input_data.get("user_id", "demo_user")
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

    user_id = input_data.get("user_id", "demo_user")
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


@app.post("/v1/onboarding/apply")
async def apply_onboarding(req: ApplyOnboardingRequest) -> dict[str, Any]:
    """Persist a wizard-collected GoalsOnboardingResult directly, skipping the LLM.

    Returns the created/superseded IPS's ips_id and version so the frontend can
    confirm real persistence rather than fabricating success.
    """
    try:
        new_ips, liab = write_ips_from_interview_result(
            user_id=req.result.user_id,
            result=req.result,
            trigger=req.trigger,
            approval_required_above_usd=req.approval_required_above_usd,
            approval_required_above_percent=req.approval_required_above_percent,
        )
    except Exception as e:
        logger.exception("onboarding apply failed for user %s", req.result.user_id)
        raise HTTPException(status_code=500, detail=f"apply_failed: {e}") from e
    return {
        "status": "applied",
        "ips_id": new_ips.ips_id,
        "version": new_ips.version,
        "liabilities_count": len(liab.liabilities),
    }


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
