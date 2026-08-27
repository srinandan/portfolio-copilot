# ADR-0019: Distributed Tracing Across the SPA, Go Server, and Orchestrator

## Status
Accepted

## Context

OpenTelemetry and Cloud Trace are enabled on the Python orchestrator running in
Agent Runtime (#280 / #284) — it emits GenAI spans. But the two hops in front of
it were dark: the Vue 3 SPA and the Cloud Run Go server (`frontend/server`)
emitted no spans and propagated no trace context. A request therefore produced,
at best, a disconnected orchestrator trace with no link back to the browser
click or the server that proxied it.

The goal is a single, correlated trace from browser click → Go server →
orchestrator, using **W3C Trace Context** (`traceparent`) as the propagation
format across the three languages.

Two design tensions shaped this ADR:

1. **The SSE streaming reader.** The dashboard consumes `/api/plan` as a
   `fetch`-based `ReadableStream` (see `readSSEStream`, ADR-0018). The obvious
   browser instrumentation, `@opentelemetry/instrumentation-fetch`, monkeypatches
   the global `fetch` and wraps the response body — which risks interfering with
   that streaming reader. Trace instrumentation must not endanger the app's core
   streaming path.

2. **Authenticating browser telemetry.** A browser cannot hold GCP credentials,
   so it cannot write to Cloud Trace directly; its spans must reach the backend
   somehow.

## Decision

### 1. Go server (`frontend/server`, `pkg/`) — full OpenTelemetry
- **TracerProvider + selectable exporter** in `telemetry.go`
  (`InitTracing`). The transport is chosen at startup: **OTLP** (`otlptracehttp`)
  when an OTLP endpoint is configured (`OTEL_EXPORTER_OTLP_ENDPOINT`,
  `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`, or `OTEL_TRACES_EXPORTER=otlp`),
  otherwise the **Google Cloud Trace exporter** (the zero-config default).
  Export is **gated**: enabled when a destination exists (an OTLP endpoint or a
  resolvable GCP project) and not disabled via `OTEL_TRACES_ENABLED=false`;
  otherwise a no-op provider is installed.
- **The W3C propagator is installed unconditionally** — even when span export is
  off — so trace context keeps flowing across services in every environment.
- **Server spans** via `otelgin.Middleware`, which extracts the incoming
  `traceparent` and starts the request span as its child.
- **Client propagation** to the orchestrator by giving the orchestrator HTTP
  client an `otelhttp.NewTransport`. It creates a client span and injects
  `traceparent` on both the direct and Agent Engine paths, and streams the SSE
  body through unbuffered (so it does not disturb the proxy).
- **Data-layer spans** in `pkg/store` (`store.Get*`) and `pkg/bigquery`
  (`bigquery.RunSecureQuery`), nesting Firestore/BigQuery work under the request.
- **IAM**: `roles/cloudtrace.agent` granted to `portfolio-copilot-frontend-sa`
  in `scripts/setup_cloudrun.sh`.

### 2. Vue SPA (`frontend/src`) — a lightweight, dependency-free tracer
`services/tracing.ts` implements W3C trace-id/span-id generation, a span model,
user-action and client spans, and OTLP-JSON batch export. It deliberately does
**not** use `@opentelemetry/sdk-trace-web` + `instrumentation-fetch`:

- Trace context is injected **header-only**, in the API layer
  (`services/api.ts`), rather than by patching global `fetch` — so the SSE reader
  is untouched (tension #1).
- It adds **zero runtime dependencies** and a negligible bundle delta, and is
  straightforward to unit-test under jsdom. The full web SDK's weight and
  instrumentation machinery bought nothing here that W3C + OTLP-JSON doesn't.

User actions (`planning_turn_triggered`, `hitl_decision_submitted`) are recorded
as spans; the API client spans for the requests they trigger nest under them.

### 3. Browser span sink — real spans re-emitted on the Go server
The SPA batches spans to `POST /api/telemetry/v1/traces` (its own dependency-free
JSON shape — tension #1 keeps the browser off the web SDK). When span export is
enabled, the Go handler (`TelemetryIngest`) **re-emits each valid span as a real
span** through a dedicated replay `TracerProvider`, preserving the SPA-supplied
`traceId`/`spanId`/`parentSpanId` via a seeded `IDGenerator`. Preserving the ids
matters: the server request span is already parented (via the propagated
`traceparent`) to the browser **client** span's id, so re-emitting that client
span with its original id gives the server span a real parent instead of an
orphan — a complete browser→server→orchestrator tree in **one** Cloud Trace
timeline (tension #2). The server does the OTLP construction so the browser stays
dependency-free.

The original design forwarded browser spans as trace-correlated **logs**
(`logging.googleapis.com/trace` + `spanId`) rather than real spans; that path is
retained as the **fallback** when span export is disabled (local dev / no
destination), so client spans still correlate by log linkage there. Upgrading the
ingest to real spans — over whichever transport §1 selected, including OTLP
forwarding to a collector — is #313; the ingest endpoint was the seam for it.

### Telemetry is advisory
As with progress events (ADR-0018), tracing must never break the page or a
request: `report`/`flush`/`ingest` failures are swallowed, malformed browser
spans are skipped (not fatal), and disabled export still propagates context.

## Consequences
- **End-to-end correlation**: a browser click, the Go server span, the
  orchestrator spans, and Firestore/BigQuery calls share one Trace ID in Cloud
  Trace.
- **Works everywhere**: propagation is always on; export degrades to a no-op
  with no project, so local dev and tests are unaffected.
- **Small footprint**: no new SPA dependencies (~+3 KB gzip); the Go side adds
  the Cloud Trace exporter, otelgin, and otelhttp.
- **Streaming stays safe**: header-only injection on the client and an
  unbuffered `otelhttp` transport on the server keep the SSE path intact
  (verified by the existing SSE proxy/stream tests).
- **Browser spans are native spans (#313)**: when export is enabled, browser
  spans are re-emitted as real spans (ids preserved) over the selected transport —
  OTLP to a collector, or the Cloud Trace exporter — rather than correlating only
  via log linkage. The log-linkage path remains as the no-export fallback. The SPA
  is still dependency-free; the OTLP construction happens server-side. Originally
  deferred to keep the surface small; the ingest endpoint was left as the seam and
  is where this landed.
- **Orchestrator egress (follow-up)**: once Firestore access moved to the remote
  Firestore MCP server (#309), the orchestrator's own outbound hop needed the same
  treatment the Go server got. `server.py` now instruments outbound `httpx`
  (`HTTPXClientInstrumentor`) — the Python analogue of §1's `otelhttp` transport —
  so the MCP call emits a CLIENT span and injects `traceparent`, extending the
  single Trace ID through the orchestrator → Firestore MCP hop.
- **Vertex `:streamQuery` breaks header propagation (follow-up)**: in Agent Engine
  mode the gateway calls Vertex `:streamQuery`, and Vertex terminates that call and
  re-issues its own request to the container — so the `traceparent` `otelhttp`
  injects on the gateway→Vertex request never reaches the orchestrator, which then
  parents its work under an *unexported* Vertex span (a "Missing span ID" root, in a
  separate Trace ID). The fix carries the W3C context **in the request body** as
  well: the gateway injects `trace_context` into the `:streamQuery` envelope
  (`plan.go`), and the orchestrator roots the `:streamQuery`/`:query` handlers from
  that body context instead of the header (`server.py`, those routes excluded from
  header-based ingress). This restores one Trace ID from browser click through the
  orchestrator even across the Vertex proxy hop. Direct (`ORCHESTRATOR_URL`) mode is
  unaffected — its `/v1/*` routes keep normal header-based ingress spans.
- **ADK-native per-request telemetry (follow-up, #364)**: ADK 2.8.0 emits
  per-invocation **token-spend** and per-workflow inference/tool-call metrics,
  gated behind experimental telemetry (default OFF). We opt in per request via
  `RunConfig.telemetry` rather than a bare process-global env var, so it is a
  code-controlled, testable setting: `adk_telemetry.build_adk_run_config()`
  returns a `RunConfig(telemetry=TelemetryConfig(adk_experimental_telemetry_opt_in=True))`
  when `ORCHESTRATOR_ADK_TELEMETRY_ENABLED` is truthy, and `server.py` threads it
  into every `run_async` call site (`None` selects the default, so a fresh deploy
  is unchanged). These metrics export through the OTel MeterProvider the server's
  telemetry setup already installs. This first step only flips the opt-in;
  reconciling the hand-rolled spans above against ADK's native invocation span
  (de-duplication) and surfacing token-spend to the product for the #169 cost cap
  are deliberately left as larger, separate follow-ups.
- **Numbering note**: issue #286 referenced "ADR-0022"; this is filed as the
  next sequential number, 0019.
