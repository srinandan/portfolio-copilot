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
- **TracerProvider + Cloud Trace exporter** in `telemetry.go`
  (`InitTracing`), using the Google Cloud Trace exporter. Export is **gated**:
  enabled when a GCP project is resolvable and not disabled via
  `OTEL_TRACES_ENABLED=false`; otherwise a no-op provider is installed.
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

### 3. Browser span sink — trace-correlated logs on the Go server
The SPA batches spans to `POST /api/telemetry/v1/traces`. The Go handler
(`TelemetryIngest`) records each valid span as a structured log entry carrying
the Cloud Logging trace-correlation fields (`logging.googleapis.com/trace`,
`logging.googleapis.com/spanId`). Because the server continues the SPA's trace
via the propagated `traceparent`, these client spans surface in the **same Cloud
Trace timeline** as the server and orchestrator spans (tension #2), reusing the
existing structured-logging pipeline rather than standing up an OTLP receiver.
Forwarding the raw OTLP to Cloud Trace's OTLP endpoint is a possible future
extension; the ingest endpoint is the seam for it.

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
- **Trade-off**: browser spans are captured as trace-correlated logs rather than
  native Cloud Trace spans. They correlate in the trace view via log linkage;
  full OTLP forwarding was deferred to keep the surface small and dependency-free.
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
- **Numbering note**: issue #286 referenced "ADR-0022"; this is filed as the
  next sequential number, 0019.
