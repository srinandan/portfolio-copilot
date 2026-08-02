# ADR-0013: IAM-Authenticated Cloud Run Invocations

## Status
Accepted

## Context
Initial scaffolding deployed the Cloud Run services (`portfolio-copilot-gateway` and `portfolio-copilot-frontend`) with `--allow-unauthenticated`. Once the gateway proxies requests to the root orchestrator (which accesses Alpaca trading credentials and Firestore portfolio records), leaving the gateway open to unauthenticated public requests creates an unacceptable security exposure.

## Decision

1. **Enforce Authenticated Cloud Run Invocations (`--no-allow-unauthenticated`)**:
   - Both `portfolio-copilot-gateway` and `portfolio-copilot-frontend` are deployed with `--no-allow-unauthenticated` in all deployment scripts (`scripts/setup_cloudrun.sh`) and CI/CD pipelines (`gateway/cloudbuild.yaml`).

2. **Grant Machine-to-Machine Invoker Role**:
   - The frontend service account (`portfolio-copilot-frontend-sa@${PROJECT_ID}.iam.gserviceaccount.com`) is granted `roles/run.invoker` on the `portfolio-copilot-gateway` Cloud Run service.
   - The frontend authenticates its backend API calls to the gateway by attaching a Google-signed OpenID Connect (OIDC) identity token minted for its service account.

3. **End-User Ingress Auth as Follow-Up**:
   - The frontend Cloud Run service is currently deployed with `--no-allow-unauthenticated` without public invoker permissions. This makes it temporarily unreachable directly from public web browsers.
   - End-user authentication (e.g., Identity-Aware Proxy (IAP) or Firebase Auth) will be configured in a subsequent task to govern human ingress into the frontend.

## Tradeoffs and Alternatives

- **`--allow-unauthenticated` with Application-Level Auth**:
  - Rejected: Leaves Cloud Run instances exposed to public request flooding and bypass risks. Using Cloud Run's native IAM layer provides defense-in-depth before application logic executes.
- **Identity-Aware Proxy (IAP) between Frontend and Gateway**:
  - Rejected for service-to-service calls: IAP is designed for human browser sessions. Cloud Run IAM with OIDC bearer tokens is the standard, zero-overhead mechanism for service-to-service authentication in GCP.

## Consequences
- **Security**: The gateway and frontend are protected against unauthenticated internet traffic.
- **Access**: Invoking the gateway requires valid GCP credentials or IAM impersonation (`gcloud auth print-identity-token`).
