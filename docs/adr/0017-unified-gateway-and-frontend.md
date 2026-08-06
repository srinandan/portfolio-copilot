# ADR-0017: Unified Gateway and Frontend Service Architecture

## Status
Accepted (Supersedes ADR-0013's split frontend/gateway deployment model)

## Context
Previously, `frontend` and `gateway` were deployed as two separate Cloud Run services:
1. `portfolio-copilot-frontend`: Ran a Go binary serving Vue 3 static assets and reverse-proxying `/api/*` to the gateway with minted IAM ID tokens.
2. `portfolio-copilot-gateway`: Handled API routes, SSE streaming, Firestore, BigQuery, and Vertex AI Agent Runtime orchestration.

This split introduced significant friction:
- Required cross-service machine-to-machine IAM tokens (`roles/run.invoker`, `roles/iam.serviceAccountTokenCreator`).
- Incurred duplicate latency, token-minting overhead, and potential audience mismatch failures.
- Maintained two separate Cloud Run services, two Cloud Build pipelines, and two service accounts.

Because the frontend already relied on a Go container runtime to serve static files and proxy requests, hosting the compiled Vue SPA directly inside the Go gateway eliminates the internal network hop entirely.

## Decision

1. **Single Unified Cloud Run Service (`portfolio-copilot-gateway`)**:
   - The Go gateway serves both the compiled Vue 3 SPA static assets (`dist/`) and all API routes (`/api/*`, `/health`) in a single process.
   - SPA routing: Non-API routes serve static files with fallback to `index.html` for Vue Router history mode; missing static files with extensions 404 cleanly.
   - In-process execution: API calls execute directly against Go handlers without network proxying or token minting between frontend and gateway.

2. **Multi-Stage Container Build**:
   - Stage 1 (Node): Builds the Vue SPA via `npm run build` into `dist/`.
   - Stage 2 (Go): Compiles the Go gateway binary.
   - Stage 3 (Distroless): Packages the Go binary and `dist/` assets into a minimal container.

3. **Preserved Local Development Workflows**:
   - Frontend developers can run `npm run dev` (port 3000) with Vite dev proxy pointing to `localhost:8080`.
   - Full-stack testing can run `make -C gateway local` on port 8080 serving both UI and API.

## Consequences

- **Simplicity**: Reduces Cloud Run services from 2 to 1, service accounts from 2 to 1, and Cloud Build triggers from 3 to 2.
- **Reliability**: Eliminates all cross-service token generation, header forwarding, and audience validation failure points.
- **Performance**: Zero network overhead between UI asset delivery and backend API execution.
- **Security**: The unified gateway service remains protected by Cloud Run IAM (`--no-allow-unauthenticated`).
