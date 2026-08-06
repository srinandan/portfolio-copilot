# Portfolio Copilot Gateway

The Go API Gateway for **Portfolio Copilot**, serving as the single entry point between the standalone web frontend (`frontend/`) and the backend Python orchestrator and data stores.

Written in **Go 1.25+** and deployable as a containerized microservice on **Google Cloud Run**.

See [ADR-0003](../docs/adr/0003-standalone-ui-not-agentspace.md) and [ADR-0013](../docs/adr/0013-api-gateway-pattern.md) for why the gateway is a dedicated Go service separate from the Python ADK orchestrator.

---

## What It Does

- **API Entry Point & Decoupling (F7 Contract)**: Provides HTTP/REST endpoints and Server-Sent Events (SSE) streaming for the frontend Single-Page Application (SPA). Protects the Python orchestrator from direct internet exposure and client-side implementation details.
- **Least-Privilege Cloud IAM Authentication**:
  - Uses Google Cloud Application Default Credentials (ADC) via `golang.org/x/oauth2/google`.
  - Configured with narrow IAM policy bindings per [`scripts/setup_cloudrun.sh`](../scripts/setup_cloudrun.sh) (`roles/datastore.user` for Firestore holding reads and audit log writes; `roles/bigquery.dataViewer` for analytical chart reads).
  - Does **not** access Secret Manager or broker Alpaca API credentials directly (ADR-0005 — broker integration is strictly an orchestrator-only concern).
- **Structured JSON Logging**: Implements middleware (`StructuredLogMiddleware`) using Go's `log/slog` standard library for Cloud Logging compatibility.
- **Server-Sent Events (SSE) Streaming**: Exposes real-time event streams (`/api/stream`) for conversational agent planning messages, governance proposals, and live audit notifications.
- **Cloud Run Health Probes**: Provides `/health` for liveness and readiness health checks.

---

## Project Structure

```
gateway/
├── Dockerfile              # Multi-stage Docker build (Golang 1.25 builder -> distroless static)
├── README.md               # Gateway documentation
├── cloudbuild.yaml         # Cloud Build CI/CD pipeline configuration
├── main.go                 # Gin server setup, ADC auth checks, SSE streaming, and health probe
├── middleware.go           # Structured logging middleware (slog + Gin)
└── middleware_test.go      # Table-driven unit tests for middleware and HTTP handlers
```

---

## Prerequisites

- **Go 1.25+**
- Google Cloud SDK (`gcloud`) configured if authenticating against live GCP projects

---

## Local Setup & Installation

Navigate to the repository root or the `gateway` directory:

```bash
cd gateway
```

Download Go module dependencies:

```bash
go mod download
```

### Running Locally

Run the API gateway server locally on port `8080`:

```bash
make -C gateway local        # or: go run ./gateway
```

By default, the server binds to `0.0.0.0:8080`.

---

## Running Tests

Run all unit tests in the `gateway` module:

```bash
go test -v ./...
```

Run tests with code coverage reporting:

```bash
go test ./... -cover
```

> **Testing & Coverage Expectations**:
> - Follow [`.agent/skills/unit-testing/SKILL.md`](../.agent/skills/unit-testing/SKILL.md): Use **table-driven Go tests** (`struct { name string; ... }`) with `httptest.NewRecorder` for HTTP handler verification.
> - Per [`.agent/skills/code-coverage/SKILL.md`](../.agent/skills/code-coverage/SKILL.md), `gateway/` tests should maintain comprehensive coverage of handler logic, middleware error paths, and ADC auth handling.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness and readiness probe for Google Cloud Run (`200 OK`). |
| `GET` | `/api/auth-check` | Verifies Google Cloud Application Default Credentials (ADC) and project configuration. |
| `GET` | `/api/stream` | Server-Sent Events (SSE) stream — legacy heartbeat scaffold. |
| `POST` | `/api/plan` | Starts a planning turn on the orchestrator. Body: `{"user_id","message","session_id"?}`. Streams ADK events back as SSE (`data: <event-json>\n\n`). |
| `POST` | `/api/plan/resume` | Resumes a HITL-paused session. Body: `{"user_id","session_id","invocation_id","interrupt_id","payload"}`. Streams ADK events back as SSE. |

### `/api/plan` backend selection

`/api/plan` and `/api/plan/resume` proxy to the orchestrator. Backend is picked by env var:

- **`ORCHESTRATOR_URL`** (dev / local) — HTTP URL of the orchestrator's FastAPI server (e.g. `http://localhost:8080`). The gateway `POST`s to `<URL>/v1/invoke` and `<URL>/v1/resume` and streams the SSE response back unchanged.
- **`AGENT_ENGINE_ID`** (cloud) — full Vertex AI Agent Engine resource name, e.g. `projects/<num>/locations/us-central1/reasoningEngines/<id>`. The gateway calls `https://<region>-aiplatform.googleapis.com/v1beta1/<name>:streamQuery` with an ADC bearer token, wraps the frontend body in the reasoning-engine input envelope, and re-emits each streamed JSON object as one SSE `data:` frame.

If neither env var is set, both routes return `503`.

---

## Docker & Cloud Run Deployment

The gateway is containerized using a multi-stage `Dockerfile`:
1. **Builder Stage**: Compiles a static Linux binary (`CGO_ENABLED=0 GOOS=linux`) using `golang:1.25`.
2. **Runtime Stage**: Uses Google's minimal `gcr.io/distroless/static:nonroot` base image running as nonroot (`USER nonroot:nonroot`) on port `8080`.

### Deploying via the Makefile

```bash
make -C gateway deploy
```

This calls `gcloud builds submit --config=gateway/cloudbuild.yaml` with `_COMMIT_SHA=$(git rev-parse --short HEAD)` and the active gcloud region, builds+pushes the image to Artifact Registry, and deploys it to Cloud Run under the `portfolio-copilot-gateway-sa` service account created by `scripts/setup_cloudrun.sh`.

For tag-based automatic releases, see [`install/README.md`](../install/README.md) — pushing `v*` git tags fires the triggers created by `scripts/setup_cloudbuild_triggers.sh`.

---

## Related Specifications & Architecture

- **[ADR-0003](../docs/adr/0003-standalone-ui-not-agentspace.md)**: Why standalone Go API Gateway + Vue UI instead of AgentSpace
- **[ADR-0008](../docs/adr/0008-python-for-orchestrator.md)**: Python for ADK orchestrator, Go for non-agent services
- **[ADR-0013](../docs/adr/0013-api-gateway-pattern.md)**: API Gateway pattern decoupling UI from orchestrator
- **[Architecture Spec](../docs/spec/02-architecture.md)**: Overall system topology and component diagrams
- **[Contracts Spec](../docs/spec/03-contracts.md)**: Shared data models between Gateway, Firestore, and Orchestrator
