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
