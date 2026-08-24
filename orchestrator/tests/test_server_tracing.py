"""Verifies the FastAPI ingress continues an inbound W3C trace.

The Go gateway injects a `traceparent` on its call to the orchestrator (ADR-0019);
`_init_server_tracing` must extract it and open the request's server span as a
child of that remote context, so the orchestrator's spans share the browser -> Go
Trace ID rather than starting a fresh trace.

It also verifies the *egress*: the orchestrator's Firestore access is a remote MCP
call over httpx, so that hop must emit a CLIENT span and inject `traceparent`, or
the Firestore MCP server starts a fresh trace and its work never correlates.
"""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from src.orchestrator import server


def _install_exporter() -> InMemorySpanExporter:
    """Attaches an in-memory exporter to the global provider (creating a real SDK
    provider if the default proxy is still installed). Robust to test ordering."""
    exporter = InMemorySpanExporter()
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter


def test_ingress_continues_inbound_traceparent():
    exporter = _install_exporter()
    client = TestClient(server.app)

    trace_id = "0af7651916cd43dd8448eb211c80319c"
    parent_span_id = "b7ad6b7169203331"
    # /livez is dependency-free and always 200 — ideal to exercise pure ingress.
    resp = client.get("/livez", headers={"traceparent": f"00-{trace_id}-{parent_span_id}-01"})
    assert resp.status_code == 200

    server_spans = [
        s
        for s in exporter.get_finished_spans()
        if s.kind == trace.SpanKind.SERVER and format(s.context.trace_id, "032x") == trace_id
    ]
    assert server_spans, "expected a SERVER span continuing the inbound trace id"
    span = server_spans[0]
    # It is a child of the inbound (browser->Go) span, so the whole trace is one.
    assert span.parent is not None
    assert format(span.parent.span_id, "016x") == parent_span_id


def test_ingress_starts_span_without_inbound_traceparent():
    """With no inbound traceparent the ingress still opens a server span (a fresh
    trace root) — tracing works, it just has no upstream to continue."""
    exporter = _install_exporter()
    client = TestClient(server.app)

    resp = client.get("/livez")
    assert resp.status_code == 200
    server_spans = [s for s in exporter.get_finished_spans() if s.kind == trace.SpanKind.SERVER]
    assert server_spans, "expected a SERVER span even without an inbound traceparent"


def test_service_name_default_and_override(monkeypatch):
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
    assert server._service_name() == "portfolio-copilot-orchestrator"
    monkeypatch.setenv("OTEL_SERVICE_NAME", "custom-orchestrator")
    assert server._service_name() == "custom-orchestrator"


def test_resolve_project_id_precedence(monkeypatch):
    # Neutralize ADC so this test exercises env-var precedence in isolation.
    monkeypatch.setattr(server, "_project_from_adc", lambda: "")
    for k in (
        "OTEL_EXPORTER_GCP_TRACE_PROJECT_ID",
        "GOOGLE_CLOUD_PROJECT",
        "PROJECT_ID",
        "FIRESTORE_PROJECT_ID",
    ):
        monkeypatch.delenv(k, raising=False)
    assert server._resolve_project_id() == ""
    monkeypatch.setenv("FIRESTORE_PROJECT_ID", "fs-proj")
    assert server._resolve_project_id() == "fs-proj"
    monkeypatch.setenv("PROJECT_ID", "my-app-proj")
    assert server._resolve_project_id() == "my-app-proj"
    monkeypatch.setenv("OTEL_EXPORTER_GCP_TRACE_PROJECT_ID", "otel-proj")
    assert server._resolve_project_id() == "otel-proj"


def test_resolve_project_id_rejects_numeric_project_number(monkeypatch):
    """Cloud Trace rejects numeric project numbers (e.g. 432423772502) with 400.

    When Agent Runtime automatically populates GOOGLE_CLOUD_PROJECT with the
    numeric project number, _resolve_project_id must prefer the string PROJECT_ID.
    """
    monkeypatch.setattr(server, "_project_from_adc", lambda: "")
    for k in (
        "OTEL_EXPORTER_GCP_TRACE_PROJECT_ID",
        "GOOGLE_CLOUD_PROJECT",
        "PROJECT_ID",
        "FIRESTORE_PROJECT_ID",
    ):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "432423772502")
    monkeypatch.setenv("PROJECT_ID", "srinandans-next25-demo")
    assert server._resolve_project_id() == "srinandans-next25-demo"


def test_resolve_project_id_falls_back_to_adc(monkeypatch):
    """With no usable string ID in env, the project must be recovered from ADC so
    span export is not silently disabled — an Agent Runtime container always has
    Agent Identity credentials even when PROJECT_ID was not injected."""
    for k in (
        "OTEL_EXPORTER_GCP_TRACE_PROJECT_ID",
        "PROJECT_ID",
        "FIRESTORE_PROJECT_ID",
        "GOOGLE_CLOUD_PROJECT",
    ):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(server, "_project_from_adc", lambda: "adc-resolved-proj")
    assert server._resolve_project_id() == "adc-resolved-proj"

    # A numeric project *number* in env must not shadow the ADC string ID that
    # Cloud Trace will actually accept.
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "432423772502")
    assert server._resolve_project_id() == "adc-resolved-proj"


def test_ensure_service_name_fills_unknown_and_reaches_later_spans(monkeypatch):
    """Reused-provider case (Agent Runtime installed the provider): its resource
    carries the default ``unknown_service``, so exported spans show no service
    name. Stamping our name onto the resource before request-time tracers are
    created must make later spans carry it — the regression behind 'no service
    name associated with these traces'."""
    from opentelemetry.sdk.resources import SERVICE_NAME
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    provider = TracerProvider()  # default resource => service.name == "unknown_service"
    assert str(provider.resource.attributes.get(SERVICE_NAME)).startswith("unknown_service")

    server._ensure_service_name(provider)
    assert provider.resource.attributes.get(SERVICE_NAME) == "portfolio-copilot-orchestrator"

    # A tracer created AFTER the stamp (as FastAPI/ADK are at request time) must
    # emit spans carrying the stamped service.name.
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    with provider.get_tracer("google.adk").start_as_current_span("invoke_workflow"):
        pass
    provider.force_flush()
    spans = exporter.get_finished_spans()
    assert spans and spans[0].resource.attributes.get(SERVICE_NAME) == "portfolio-copilot-orchestrator"


def test_ensure_service_name_preserves_real_name():
    """A deliberate upstream service.name must not be overwritten."""
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource

    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: "upstream-set-name"}))
    server._ensure_service_name(provider)
    assert provider.resource.attributes.get(SERVICE_NAME) == "upstream-set-name"


def test_build_tracer_provider_carries_service_name_and_exports():
    """The provider we install must (a) tag spans with our service.name resource so
    they are attributable in Cloud Trace, and (b) actually export ended spans."""
    exporter = InMemorySpanExporter()
    provider = server._build_tracer_provider("portfolio-copilot-orchestrator", exporter)

    assert provider.resource.attributes.get("service.name") == "portfolio-copilot-orchestrator"

    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span("unit-span"):
        pass
    provider.force_flush()

    spans = exporter.get_finished_spans()
    assert [s.name for s in spans] == ["unit-span"]
    assert spans[0].resource.attributes.get("service.name") == "portfolio-copilot-orchestrator"


def test_reasoning_stream_roots_span_at_body_trace_context():
    """Agent Engine :streamQuery is Vertex-proxied, so the real trace context
    arrives in the request BODY (``trace_context``), not a header. The reasoning
    stream must root its SERVER span under that context — and ADK spans created
    while the stream is iterated must nest under it — so the orchestrator rejoins
    the browser -> Go trace instead of a 'Missing span' Vertex root."""
    import asyncio

    exporter = _install_exporter()
    trace_id = "0af7651916cd43dd8448eb211c80319c"
    gateway_span = "b7ad6b7169203331"
    body = {"input": {"user_id": "u"}, "trace_context": {"traceparent": f"00-{trace_id}-{gateway_span}-01"}}
    parent_ctx = server._extract_body_trace_context(body)

    async def _inner():
        # An ADK span emitted DURING streaming must land under the server span.
        trace.get_tracer("google.adk").start_span("invoke_workflow").end()
        yield b'{"x":1}\n'

    async def _drain():
        return [
            c async for c in server._traced_reasoning_stream(_inner(), parent_ctx, "POST /api/stream_reasoning_engine")
        ]

    chunks = asyncio.run(_drain())
    assert chunks == [b'{"x":1}\n']

    spans = {s.name: s for s in exporter.get_finished_spans()}
    srv = spans["POST /api/stream_reasoning_engine"]
    assert format(srv.context.trace_id, "032x") == trace_id
    assert srv.parent is not None and format(srv.parent.span_id, "016x") == gateway_span
    # ADK work created during iteration shares the trace and nests under the server span.
    adk = spans["invoke_workflow"]
    assert adk.context.trace_id == srv.context.trace_id
    assert adk.parent is not None and adk.parent.span_id == srv.context.span_id


def test_extract_body_trace_context_absent_or_invalid_returns_none():
    """No/blank/invalid trace_context => None (the stream then roots a fresh trace),
    never an exception."""
    assert server._extract_body_trace_context({"input": {}}) is None
    assert server._extract_body_trace_context({"trace_context": {}}) is None
    assert server._extract_body_trace_context({"trace_context": "nope"}) is None
    assert server._extract_body_trace_context("not-a-dict") is None


def test_outbound_httpx_emits_client_span_and_injects_traceparent():
    """The Firestore Remote MCP hop is an outbound httpx call. After
    ``_instrument_outbound_http`` it must (a) emit a CLIENT span under the active
    trace and (b) inject ``traceparent`` so the MCP server continues our trace
    (the regression this suite guards: an uninstrumented client did neither, so
    the Firestore MCP work never showed up in Cloud Trace)."""
    exporter = _install_exporter()
    # Idempotent: httpx is already instrumented at import via _init_server_tracing.
    server._instrument_outbound_http()

    received: dict[str, str | None] = {}

    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802 (http.server API)
            received["traceparent"] = self.headers.get("traceparent")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *_args):
            pass

    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("execute_tool firestore.query") as parent:
            parent_trace_id = format(parent.get_span_context().trace_id, "032x")
            with httpx.Client() as client:
                resp = client.post(f"http://127.0.0.1:{port}/mcp", json={"method": "tools/call"})
                assert resp.status_code == 200
    finally:
        srv.shutdown()
        thread.join(timeout=5)

    # (a) A CLIENT span for the outbound call, sharing the active trace id.
    client_spans = [
        s
        for s in exporter.get_finished_spans()
        if s.kind == trace.SpanKind.CLIENT and format(s.context.trace_id, "032x") == parent_trace_id
    ]
    assert client_spans, "expected a CLIENT span for the outbound MCP-style httpx call"

    # (b) traceparent injected onto the request, carrying our trace id.
    traceparent = received.get("traceparent")
    assert traceparent, "expected traceparent to be injected onto the outbound request"
    assert traceparent.split("-")[1] == parent_trace_id


def test_patch_opentelemetry_context_detach_suppresses_cross_context_value_error():
    """Verify that when a token created in another Context is detached, the
    resulting 'was created in a different Context' ValueError is safely caught."""
    import contextvars

    from opentelemetry.context.contextvars_context import ContextVarsRuntimeContext

    server._patch_opentelemetry_context_detach()
    runtime_ctx = ContextVarsRuntimeContext()

    token = None

    def _in_other_context():
        nonlocal token
        token = runtime_ctx.attach({"test_key": "test_val"})

    # Run in a separate context to generate a token tied to that other context.
    ctx = contextvars.copy_context()
    ctx.run(_in_other_context)

    assert token is not None
    # In this context, detaching token from another context would normally raise
    # ValueError("<Token ...> was created in a different Context").
    # With the patch, it must return silently without raising.
    runtime_ctx.detach(token)


def test_patch_opentelemetry_context_detach_re_raises_unrelated_value_error(monkeypatch):
    """Verify that unrelated ValueErrors are not swallowed."""
    import pytest
    from opentelemetry.context.contextvars_context import ContextVarsRuntimeContext

    # Unpatch temporarily to install a mock that throws an unrelated ValueError
    orig_fn = ContextVarsRuntimeContext.detach
    if hasattr(orig_fn, "_is_safe_patched"):
        # Reset patch marker for test
        delattr(orig_fn, "_is_safe_patched")

    def _broken_detach(self, token):
        raise ValueError("unrelated failure")

    monkeypatch.setattr(ContextVarsRuntimeContext, "detach", _broken_detach)
    server._patch_opentelemetry_context_detach()

    runtime_ctx = ContextVarsRuntimeContext()
    with pytest.raises(ValueError, match="unrelated failure"):
        runtime_ctx.detach("dummy_token")


def test_patch_opentelemetry_context_detach_is_idempotent():
    """Verify that multiple invocations of _patch_opentelemetry_context_detach are safe."""
    from opentelemetry.context.contextvars_context import ContextVarsRuntimeContext

    server._patch_opentelemetry_context_detach()
    first_fn = ContextVarsRuntimeContext.detach
    server._patch_opentelemetry_context_detach()
    second_fn = ContextVarsRuntimeContext.detach
    assert first_fn is second_fn

