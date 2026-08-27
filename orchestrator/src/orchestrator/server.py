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
from pydantic import BaseModel, field_validator

from .adk_telemetry import build_adk_run_config
from .contracts.goals_onboarding import GoalsOnboardingResult
from .data.validation import validate_user_id
from .guardrails import (
    build_model_armor_plugin,
    guardrail_block_frame,
    wire_is_model_armor_block,
)
from .logger import get_logger
from .planner import root_agent
from .progress import PROGRESS_CHANNEL
from .session_manager import SessionManager
from .state import (
    PreloadDeclinedError,
    preload_for_equity_research,
    preload_for_suitability,
    write_ips_from_interview_result,
)

logger = get_logger(__name__)

APP_NAME = os.environ.get("AGENT_ENGINE_ID") or os.environ.get("ORCHESTRATOR_APP_NAME", "portfolio_copilot")


class InvokeRequest(BaseModel):
    user_id: str
    message: str
    session_id: Optional[str] = None

    @field_validator("user_id")
    @classmethod
    def check_user_id(cls, v: str) -> str:
        return validate_user_id(v)


class ResumeRequest(BaseModel):
    user_id: str
    session_id: str
    invocation_id: str
    interrupt_id: str
    payload: Any

    @field_validator("user_id")
    @classmethod
    def check_user_id(cls, v: str) -> str:
        return validate_user_id(v)


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


class EquityAnalysisRequest(BaseModel):
    """Request for a synchronous, deterministic single-equity advisory analysis."""

    ticker: str
    user_id: str = "demo_user"

    @field_validator("user_id")
    @classmethod
    def check_user_id(cls, v: str) -> str:
        return validate_user_id(v)


class ServerState:
    session_manager: Optional[SessionManager] = None
    runner: Optional[Runner] = None
    firestore_mcp_toolset: Optional[Any] = None
    bigquery_mcp_toolset: Optional[Any] = None
    # Per-request RunConfig opting into ADK experimental telemetry, or None
    # (default). Built once at startup from env; see adk_telemetry.py.
    adk_run_config: Optional[Any] = None
    ready: bool = False


state = ServerState()


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    from .data.bigquery_mcp import (
        get_bigquery_mcp_toolset_from_registry,
    )
    from .data.bigquery_mcp import (
        list_available_mcp_tools as list_available_bq_mcp_tools,
    )
    from .data.firestore_mcp import (
        get_firestore_mcp_toolset_from_registry,
        list_available_mcp_tools,
    )
    from .managed_agents.secret_loader import verify_required_secrets
    from .skills._skill_metadata import verify_all_skills_metadata
    from .skills.manifest import verify_all_manifests

    verify_all_skills_metadata()
    verify_all_manifests()
    verify_required_secrets()

    try:
        toolset = get_firestore_mcp_toolset_from_registry()
        try:
            tools = await asyncio.wait_for(list_available_mcp_tools(toolset), timeout=10.0)
            state.firestore_mcp_toolset = toolset
            logger.info(
                "Firestore Remote MCP Server toolset initialized successfully on startup (tools=%d).",
                len(tools),
            )
        except Exception:
            try:
                await toolset.close()
            except Exception:
                pass
            raise
    except Exception as e:
        logger.warning("Firestore Remote MCP startup check deferred: %s", e)

    try:
        bq_toolset = get_bigquery_mcp_toolset_from_registry()
        try:
            bq_tools = await asyncio.wait_for(list_available_bq_mcp_tools(bq_toolset), timeout=10.0)
            state.bigquery_mcp_toolset = bq_toolset
            logger.info(
                "BigQuery Remote MCP Server toolset initialized successfully on startup (tools=%d).",
                len(bq_tools),
            )
        except Exception:
            try:
                await bq_toolset.close()
            except Exception:
                pass
            raise
    except Exception as e:
        logger.warning("BigQuery Remote MCP startup check deferred: %s", e)

    state.session_manager = SessionManager()

    # Optional Model Armor runtime guardrail (ADR-0026). Default OFF: returns
    # None unless MODEL_ARMOR_PLUGIN_ENABLED is set and a template is configured,
    # so a fresh deploy is unaffected. Complements the project floor settings.
    guardrail_plugins = [p for p in (build_model_armor_plugin(),) if p is not None]

    state.runner = Runner(
        app_name=APP_NAME,
        agent=root_agent,
        session_service=state.session_manager.session_service,
        memory_service=state.session_manager.memory_service,
        plugins=guardrail_plugins or None,
        auto_create_session=True,
    )
    # Opt into ADK experimental telemetry (token-spend + per-workflow metrics)
    # via RunConfig, gated by env (default OFF). See ADR-0019 and adk_telemetry.py.
    state.adk_run_config = build_adk_run_config()
    state.ready = True
    logger.info("Orchestrator HTTP server ready (app_name=%s)", APP_NAME)
    try:
        yield
    finally:
        state.ready = False
        if state.firestore_mcp_toolset is not None:
            try:
                await state.firestore_mcp_toolset.close()
                logger.info("Firestore Remote MCP toolset closed successfully.")
            except Exception as e:
                logger.warning("Failed to close Firestore Remote MCP toolset on shutdown: %s", e)
            state.firestore_mcp_toolset = None
        if state.bigquery_mcp_toolset is not None:
            try:
                await state.bigquery_mcp_toolset.close()
                logger.info("BigQuery Remote MCP toolset closed successfully.")
            except Exception as e:
                logger.warning("Failed to close BigQuery Remote MCP toolset on shutdown: %s", e)
            state.bigquery_mcp_toolset = None


def _project_from_adc() -> str:
    """Best-effort GCP project ID from Application Default Credentials.

    An Agent Runtime container always runs as its Agent Identity, so ADC can
    resolve the project from the metadata server even when no ``PROJECT_ID``-style
    env var was injected. Never raises — returns "" if ADC is unavailable
    (local/tests) so callers can fall through cleanly."""
    try:
        import google.auth

        _, project = google.auth.default()
        return project or ""
    except Exception:
        return ""


def _resolve_project_id() -> str:
    """Resolves the GCP project ID string for span export.

    Cloud Trace requires an alphanumeric Project ID (e.g. 'my-project') and
    rejects numeric Project Numbers (e.g. '432423772502') with:
        400 Invalid project id in name!

    In Agent Runtime containers, GOOGLE_CLOUD_PROJECT is often automatically
    populated with the numeric project number, while PROJECT_ID carries the
    user-configured string ID. We prefer non-numeric string IDs.

    Env vars win, but if none yields a usable string ID we fall back to ADC
    (``_project_from_adc``) — so a container missing ``PROJECT_ID`` /
    ``OTEL_EXPORTER_GCP_TRACE_PROJECT_ID`` still exports instead of going silently
    dark. A numeric project number from env is the last resort.
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

    # Prefer non-numeric project ID strings over numeric project numbers.
    for c in candidates:
        if not c.isdigit():
            return c

    # No usable string ID in env — recover the project from credentials rather
    # than disabling export (Cloud Trace rejects the numeric number anyway).
    adc_project = _project_from_adc()
    if adc_project and not adc_project.isdigit():
        return adc_project

    return candidates[0] if candidates else adc_project


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


def _ensure_service_name(provider) -> None:
    """Stamp our ``service.name`` onto an existing provider's resource when it has
    none (or the OTel default ``unknown_service``).

    When Agent Runtime already installed a TracerProvider we reuse it — so ADK's
    GenAI spans keep exporting — and merely attach our Cloud Trace exporter. But
    that provider's resource carries the default ``service.name=unknown_service``,
    so its spans show **no service name** in Cloud Trace and are unattributable.

    The SDK captures the resource when each ``Tracer`` is *created* (not per span),
    and the request-time tracers (FastAPI ingress, ADK) are created after this
    runs at startup — so merging our ``service.name`` in now reaches them. The
    resource is immutable, so we replace the provider's ``_resource`` before any
    span is emitted. Only fills a missing/unknown name; a real name set upstream
    is left as-is. Never fatal.
    """
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource

    try:
        current_name = provider.resource.attributes.get(SERVICE_NAME, "")
        if (not current_name) or str(current_name).startswith("unknown_service"):
            provider._resource = provider.resource.merge(Resource.create({SERVICE_NAME: _service_name()}))
            logger.info("Stamped service.name=%s onto existing TracerProvider resource", _service_name())
    except Exception:
        logger.exception("Could not stamp service.name onto existing TracerProvider")


def _configure_span_export() -> None:
    """Ensures the orchestrator's own spans are exported to Cloud Trace / Vertex AI Telemetry.

    Ingress instrumentation alone (extracting ``traceparent`` and opening a server
    span) does not *emit* anything — it needs a TracerProvider with an exporter.
    This wires ADK's Google Cloud Telemetry exporter (OTLP to telemetry.googleapis.com)
    and Cloud Trace exporter, with proper ``cloud.resource_id`` and ``service.name``
    resources so the spans and ADK/GenAI spans nesting under it reach Cloud Trace and
    Agent Engine observability.

    If a real SDK TracerProvider already exists (e.g. one Agent Runtime installed),
    the exporter is attached to it — and we stamp our ``service.name`` onto its
    resource (``_ensure_service_name``) so the reused-provider spans are still
    attributable; otherwise a new provider carrying our ``service.name`` is
    installed. Skips silently when no project is resolvable (local/tests) —
    trace-context propagation stays active.
    """
    project_id = _resolve_project_id()
    if not project_id:
        logger.warning(
            "No GCP project resolvable (checked OTEL_EXPORTER_GCP_TRACE_PROJECT_ID, PROJECT_ID, "
            "FIRESTORE_PROJECT_ID, GOOGLE_CLOUD_PROJECT, and ADC); orchestrator span export DISABLED "
            "— no server or ADK/GenAI spans will reach Cloud Trace. Set PROJECT_ID on the deployment "
            "to fix. (Trace-context propagation stays active.)"
        )
        return

    if project_id:
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
    if os.environ.get("AGENT_ENGINE_ID"):
        os.environ.setdefault("GOOGLE_CLOUD_AGENT_ENGINE_ID", os.environ["AGENT_ENGINE_ID"])
    if os.environ.get("GOOGLE_CLOUD_LOCATION"):
        os.environ.setdefault("GOOGLE_CLOUD_AGENT_ENGINE_LOCATION", os.environ["GOOGLE_CLOUD_LOCATION"])
    os.environ.setdefault("GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY", "true")

    try:
        import google.auth
        from google.adk.telemetry.google_cloud import get_gcp_exporters, get_gcp_resource
        from google.adk.telemetry.setup import maybe_set_otel_providers
        from opentelemetry import trace as ot_trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider

        try:
            credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        except Exception:
            credentials = None

        otel_hooks = get_gcp_exporters(
            enable_cloud_tracing=True,
            enable_cloud_metrics=False,
            enable_cloud_logging=False,
            google_auth=(credentials, project_id) if credentials else None,
        )
        otel_resource = get_gcp_resource(project_id)
        service_name = _service_name()
        if service_name:
            otel_resource = otel_resource.merge(Resource.create({"service.name": service_name}))

        current = ot_trace.get_tracer_provider()
        if isinstance(current, TracerProvider):
            _ensure_service_name(current)
            for proc in otel_hooks.span_processors:
                current.add_span_processor(proc)
            logger.info(
                "Attached ADK Cloud Trace exporter to existing TracerProvider (service=%s, project=%s)",
                service_name,
                project_id,
            )
        else:
            maybe_set_otel_providers(
                otel_hooks_to_setup=[otel_hooks],
                otel_resource=otel_resource,
            )
            logger.info(
                "Installed orchestrator TracerProvider with ADK Cloud Trace exporter (service=%s, project=%s)",
                service_name,
                project_id,
            )
    except Exception:
        logger.exception("ADK Cloud Trace exporter setup failed; falling back to CloudTraceSpanExporter")
        try:
            from opentelemetry import trace as ot_trace
            from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            exporter = CloudTraceSpanExporter(project_id=project_id)
            current = ot_trace.get_tracer_provider()
            if isinstance(current, TracerProvider):
                _ensure_service_name(current)
                current.add_span_processor(BatchSpanProcessor(exporter))
                logger.info(
                    "Attached fallback Cloud Trace exporter to existing TracerProvider (service=%s, project=%s)",
                    _service_name(),
                    project_id,
                )
            else:
                ot_trace.set_tracer_provider(_build_tracer_provider(_service_name(), exporter))
                logger.info(
                    "Installed orchestrator TracerProvider with fallback Cloud Trace exporter (service=%s, project=%s)",
                    _service_name(),
                    project_id,
                )
        except Exception:
            logger.exception("Fallback Cloud Trace exporter setup failed; orchestrator span export disabled")


def _instrument_outbound_http() -> None:
    """Instrument the outbound ``httpx`` client so calls to the Firestore Remote
    MCP server participate in the trace.

    The orchestrator's Firestore access is a remote MCP call: the ADK
    ``McpToolset`` talks to ``https://firestore.googleapis.com/mcp`` over a
    Streamable-HTTP transport, which the MCP SDK backs with ``httpx``
    (``data/firestore_mcp.py``). Instrumenting the ingress and exporting spans
    (above) is not enough for *that* hop. An uninstrumented client does neither of:

    1. **emit a CLIENT span** for the outbound request (so the Firestore MCP
       call is invisible in Cloud Trace — no latency, no error attribution);
    2. **inject the W3C ``traceparent``** onto the request (so the Firestore MCP
       server starts a *fresh* trace instead of continuing ours — its spans never
       correlate with the browser -> Go -> orchestrator timeline).

    ``HTTPXClientInstrumentor`` patches httpx's transport, so every httpx client
    the process creates — including the one the MCP SDK builds internally — gets
    a client span plus header injection via the global W3C propagator. This is
    the Python analogue of the Go server's ``otelhttp.NewTransport`` on its
    orchestrator client (ADR-0019 §1), closing the same gap for the MCP hop.

    Never fatal; a telemetry failure must not stop the server from serving.
    """
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
        logger.info("Outbound httpx tracing enabled (client spans + traceparent for Firestore MCP)")
    except Exception:
        logger.exception("httpx instrumentation failed; outbound MCP calls will not be traced")


def _patch_opentelemetry_context_detach() -> None:
    """Suppresses upstream OpenTelemetry ValueError on cross-context detach.

    FastAPI/Starlette StreamingResponse yields chunks across async task
    boundaries. When OpenTelemetry's ASGI middleware runs its cleanup in
    finally:, ContextVarsRuntimeContext.detach(token) can raise:
        ValueError: <Token ...> was created in a different Context
    This is harmless teardown noise that dumps tracebacks to stderr in Agent Runtime.
    """
    try:
        from opentelemetry.context.contextvars_context import ContextVarsRuntimeContext

        orig_detach = ContextVarsRuntimeContext.detach
        if getattr(orig_detach, "_is_safe_patched", False):
            return

        def safe_detach(self, token: Any) -> None:
            try:
                orig_detach(self, token)
            except ValueError as exc:
                if "was created in a different Context" in str(exc):
                    return
                raise

        safe_detach._is_safe_patched = True  # type: ignore[attr-defined]
        ContextVarsRuntimeContext.detach = safe_detach
    except Exception:
        logger.exception("Failed to patch OpenTelemetry context detachment")


def _init_server_tracing(fastapi_app: FastAPI) -> None:
    """Instrument the FastAPI ingress AND export the orchestrator's spans to Cloud Trace.

    Three pieces are needed for the orchestrator to participate in the end-to-end
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
    3. **Outbound propagation (egress).** The orchestrator's Firestore access is a
       remote MCP call over httpx; ``_instrument_outbound_http`` gives that hop a
       CLIENT span and injects ``traceparent`` so the Firestore MCP server
       continues our trace instead of starting a fresh one.

    Opt-out via ``OTEL_TRACES_ENABLED=false``; never fatal — a telemetry failure
    must not stop the server from serving.

    Note: in Agent Engine (Vertex ``:streamQuery``) deployments the inbound
    ``traceparent`` header is Vertex's own — it terminates the gateway's call and
    re-issues its own request — so header-based ingress would parent these routes
    under an unexported Vertex span ("Missing span ID" root). The gateway therefore
    also passes the real W3C context in the request *body*; the ``:streamQuery``
    routes are excluded from header-based ingress here and instead rooted from that
    body context (``_traced_reasoning_stream``). In direct (``ORCHESTRATOR_URL``)
    mode the header always reaches ``/v1/*``, which keep normal ingress spans.
    """
    _patch_opentelemetry_context_detach()
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
        FastAPIInstrumentor.instrument_app(
            fastapi_app,
            # The Vertex :streamQuery routes carry Vertex's traceparent, not the
            # gateway's — we root them from the body-carried context instead
            # (_traced_reasoning_stream), so skip header-based ingress spans here to
            # avoid a mis-parented duplicate under the "Missing span" Vertex root.
            excluded_urls="api/stream_reasoning_engine,api/reasoning_engine",
        )
        # Instrument the egress too, so the Firestore Remote MCP hop is traced and
        # propagates context (the propagator above governs the injected headers).
        _instrument_outbound_http()
        logger.info("FastAPI server-side tracing enabled (W3C extraction + Cloud Trace export + outbound MCP)")
    except Exception:
        logger.exception("FastAPI tracing init failed; continuing without ingress spans")


app = FastAPI(title="Portfolio Copilot Orchestrator", version="0.2.0", lifespan=_lifespan)
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
                wire = _event_to_wire(event)
                queue.put_nowait(wire)
                # A Model Armor block surfaces as an LlmResponse with a
                # custom_metadata flag (ADR-0026). Emit an advisory guardrail
                # frame alongside it so the UI can render a block notice; the
                # governance audit log is untouched.
                if wire_is_model_armor_block(wire):
                    logger.warning("Model Armor blocked a turn (author=%s)", wire.get("author"))
                    queue.put_nowait(guardrail_block_frame(wire))
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


def _extract_body_trace_context(body: Any, request: Optional[Request] = None):
    """Extract W3C trace context from request headers (Google-Agent-Engine-Traceparent,
    traceparent) or the Vertex :streamQuery body carrier (trace_context / input.trace_context).

    Vertex terminates the gateway's call and may forward context via the
    ``Google-Agent-Engine-Traceparent`` header or in the request body under
    ``trace_context``. Checking headers first with body fallback ensures the
    orchestrator roots its spans under the browser -> Go span in all deployment
    modes. Returns an OTel ``Context`` to parent under, or ``None`` when absent.
    Never raises.
    """
    try:
        from opentelemetry.propagate import extract
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

        propagator = TraceContextTextMapPropagator()

        if request is not None:
            ae_header = request.headers.get("Google-Agent-Engine-Traceparent")
            if ae_header:
                return propagator.extract(carrier={"traceparent": ae_header})
            tp_header = request.headers.get("traceparent")
            if tp_header:
                return propagator.extract(carrier={"traceparent": tp_header})

        carrier = None
        if isinstance(body, dict):
            carrier = body.get("trace_context")
            if not carrier and isinstance(body.get("input"), dict):
                carrier = body["input"].get("trace_context")
        if not isinstance(carrier, dict) or not carrier:
            return None

        return extract({str(k): str(v) for k, v in carrier.items()})
    except Exception:
        logger.exception("Failed to extract body trace_context; rooting a fresh trace")
        return None


def _traced_reasoning_stream(
    inner: AsyncIterator[bytes],
    parent_ctx: Any = None,
    span_name: str = "POST /api/stream_reasoning_engine",
    span: Any = None,
    token: Any = None,
) -> AsyncIterator[bytes]:
    """Wrap a reasoning-engine byte stream in a SERVER span.

    If ``span`` and ``token`` are passed, the span was already started and
    attached before runner setup so all planner and GenAI operations nest under
    it; this generator maintains the span across streaming chunks and ends it on
    completion. If only ``parent_ctx`` is passed, starts and attaches a new span.
    """

    async def _gen() -> AsyncIterator[bytes]:
        nonlocal span, token
        if span is None:
            try:
                from opentelemetry import context as otel_context
                from opentelemetry import trace as ot_trace

                tracer = ot_trace.get_tracer("orchestrator.reasoning_engine")
                span = tracer.start_span(span_name, context=parent_ctx, kind=ot_trace.SpanKind.SERVER)
                token = otel_context.attach(ot_trace.set_span_in_context(span))
            except Exception:
                logger.exception("reasoning-engine span setup failed; streaming without it")
        try:
            async for chunk in inner:
                yield chunk
        finally:
            try:
                if token is not None:
                    from opentelemetry import context as otel_context

                    try:
                        otel_context.detach(token)
                    except ValueError:
                        pass
                if span is not None:
                    span.end()
            except Exception:
                logger.exception("reasoning-engine span teardown failed")


    return _gen()


@app.post("/api/stream_reasoning_engine")
async def stream_reasoning_engine(request: Request) -> StreamingResponse:
    """Agent Runtime (Reasoning Engine :streamQuery) endpoint."""
    if state.runner is None:
        raise HTTPException(status_code=503, detail="runner not initialized")

    body = await request.json()
    parent_ctx = _extract_body_trace_context(body, request=request)
    class_method = body.get("class_method", "invoke")
    input_data = body.get("input", body)
    if not isinstance(input_data, dict):
        input_data = {}

    user_id = input_data.get("user_id", "demo_user")
    session_id = input_data.get("session_id")
    message = input_data.get("message", "")

    span = None
    token = None
    try:
        from opentelemetry import context as otel_context
        from opentelemetry import trace as ot_trace

        tracer = ot_trace.get_tracer("orchestrator.reasoning_engine")
        span = tracer.start_span("POST /api/stream_reasoning_engine", context=parent_ctx, kind=ot_trace.SpanKind.SERVER)
        token = otel_context.attach(ot_trace.set_span_in_context(span))
    except Exception:
        logger.exception("reasoning-engine span setup failed; executing untraced")

    try:
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
                run_config=state.adk_run_config,
            )
        else:
            session = await state.session_manager.get_or_create_session(
                app_name=APP_NAME, user_id=user_id, session_id=session_id
            )
            events = state.runner.run_async(
                user_id=user_id,
                session_id=session.id,
                new_message=UserContent(parts=[Part.from_text(text=message)]),
                run_config=state.adk_run_config,
            )

        return StreamingResponse(
            _traced_reasoning_stream(_stream_json_lines(events), span=span, token=token),
            media_type="application/x-ndjson",
        )
    except Exception:
        if token is not None:
            from opentelemetry import context as otel_context

            try:
                otel_context.detach(token)
            except ValueError:
                pass
        if span is not None:
            span.end()
        raise



@app.post("/api/reasoning_engine")
async def reasoning_engine(request: Request) -> dict[str, Any]:
    """Agent Runtime (Reasoning Engine :query) non-streaming endpoint."""
    if state.runner is None:
        raise HTTPException(status_code=503, detail="runner not initialized")

    body = await request.json()
    parent_ctx = _extract_body_trace_context(body, request=request)
    input_data = body.get("input", body)
    if not isinstance(input_data, dict):
        input_data = {}

    user_id = input_data.get("user_id", "demo_user")
    session_id = input_data.get("session_id")
    message = input_data.get("message", "")

    from opentelemetry import trace as ot_trace

    tracer = ot_trace.get_tracer("orchestrator.reasoning_engine")
    # Root the request under the body-carried gateway context (Vertex strips the
    # header; see _extract_body_trace_context), so this hop stays in one trace.
    with tracer.start_as_current_span("POST /api/reasoning_engine", context=parent_ctx, kind=ot_trace.SpanKind.SERVER):
        session = await state.session_manager.get_or_create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )
        events = state.runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=UserContent(parts=[Part.from_text(text=message)]),
            run_config=state.adk_run_config,
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
        run_config=state.adk_run_config,
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


@app.post("/v1/analysis/equity")
async def analyze_equity(req: EquityAnalysisRequest) -> dict[str, Any]:
    """Synchronous, deterministic single-equity advisory analysis (no LLM).

    Runs the equity-research valuation (DCF/quality/multiples) and the
    suitability recommendation directly via the deterministic primitives — the
    same core the planner skills use — so the UI gets a fast, reliable advisory
    card without a streaming planner turn. Advisory only: it never drafts or
    executes a trade.
    """
    ticker = (req.ticker or "").strip()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")
    try:
        research = preload_for_equity_research(user_id=req.user_id, ticker=ticker)
        suitability = preload_for_suitability(user_id=req.user_id, assessment=research["assessment"])
    except PreloadDeclinedError as e:
        # No ticker match, unknown symbol, or missing IPS/holdings — a client-actionable state.
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        logger.exception("equity analysis failed for user %s / ticker %s", req.user_id, ticker)
        raise HTTPException(status_code=500, detail=f"analysis_failed: {e}") from e
    return {
        "ticker": research["ticker"],
        "assessment": research["assessment"],
        "recommendation": suitability["recommendation"],
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
        run_config=state.adk_run_config,
    )
    return StreamingResponse(_sse(events), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
