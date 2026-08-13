"""Verifies the FastAPI ingress continues an inbound W3C trace.

The Go gateway injects a `traceparent` on its call to the orchestrator (ADR-0019);
`_init_server_tracing` must extract it and open the request's server span as a
child of that remote context, so the orchestrator's spans share the browser -> Go
Trace ID rather than starting a fresh trace.
"""

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
