# ADR-0017: Unified Frontend and Gateway Service Architecture

## Status
Accepted (Supersedes ADR-0013's split frontend/gateway deployment model)

## Context
Previously, `frontend` and `gateway` were maintained as two separate top-level directories and deployed as two separate Cloud Run services:
1. `portfolio-copilot-frontend`: Ran a Go binary serving Vue 3 static assets and reverse-proxying `/api/*` to the gateway with minted IAM ID tokens.
2. `portfolio-copilot-gateway`: Handled API routes, SSE streaming, Firestore, BigQuery, and Vertex AI Agent Runtime orchestration.

This split introduced significant friction:
- Required cross-service machine-to-machine IAM tokens (`roles/run.invoker`, `roles/iam.serviceAccountTokenCreator`).
- Incurred duplicate latency, token-minting overhead, and potential audience mismatch failures.
- Maintained two separate directories with redundant Makefiles, two Cloud Run services, two Cloud Build pipelines, and two service accounts.

Consolidating the Go backend server into `frontend/server` and serving the compiled Vue SPA in-process eliminates the internal network hop and folder duplication entirely.

## Decision

1. **Consolidated Directory Structure (`frontend/`)**:
   - `frontend/src/` &rarr; Vue 3 SPA components, views, services, and state.
   - `frontend/server/` &rarr; Go backend server handling API routes (`/api/*`), health check (`/health`), Firestore, BigQuery, and orchestrator SSE streaming.
   - `frontend/Dockerfile` &rarr; Multi-stage build producing a single distroless container.
   - `frontend/cloudbuild.yaml` &rarr; Cloud Build pipeline deploying `portfolio-copilot-frontend`.
   - `frontend/Makefile` &rarr; Unified developer tasks (`make local`, `make local-server`, `make test`, `make deploy`).

2. **Single Unified Cloud Run Service (`portfolio-copilot-frontend`)**:
   - The Go server serves both the compiled Vue 3 SPA static assets (`dist/`) and all API routes (`/api/*`, `/health`) in a single process.
   - SPA routing: Non-API routes serve static files with fallback to `index.html` for Vue Router history mode; missing static files with extensions 404 cleanly.
   - In-process execution: API calls execute directly against Go handlers without network proxying or token minting.

3. **Multi-Stage Container Build**:
   - Stage 1 (Node): Builds the Vue SPA via `npm run build` into `dist/`.
   - Stage 2 (Go): Compiles `./frontend/server` binary.
   - Stage 3 (Distroless): Packages the Go binary and `dist/` assets into a minimal container.

4. **Preserved Local Development Workflows**:
   - Frontend developers can run `make local` (port 3000) with Vite dev proxy pointing to `localhost:8080`.
   - Full-stack testing can run `make local-server` on port 8080 serving both UI and API.

## Consequences

- **Simplicity**: Eliminates top-level `gateway/` folder. Reduces Cloud Run services from 2 to 1, service accounts from 2 to 1, and Cloud Build triggers from 3 to 2.
- **Reliability**: Eliminates all cross-service token generation, header forwarding, and audience validation failure points.
- **Performance**: Zero network overhead between UI asset delivery and backend API execution.
- **Security**: The unified frontend service remains protected by Cloud Run IAM (`--no-allow-unauthenticated`).
