# ADR-0011: Scoped Service Accounts for Cloud Run and Agent Identity for Agent Runtime

## Status
Accepted

## Context
Initial infrastructure scaffolding deployed Cloud Run services under default compute service accounts and provisioned Agent Runtime (Agent Engine) without identity configuration. This violates the principle of least privilege.

Different components in the Portfolio Copilot architecture have distinct operational scopes and resource access requirements:
- **Frontend Web Application (Vue/TS + Go on Cloud Run)**: Directly serves the SPA, handles user requests, audit logging to Firestore, and fan-out queries to BigQuery for charts ([ADR-0003](0003-standalone-ui-not-agentspace.md), [ADR-0017](0017-unified-gateway-and-frontend.md)). It does not execute trades or call Alpaca directly ([ADR-0005](0005-managed-agents-hybrid-evaluation.md)).
- **Orchestrator (Python on Agent Runtime)**: Executes planner logic, coordinates skills, accesses Firestore for IPS and holdings, BigQuery for spending analysis, and Alpaca API credentials from Secret Manager.

## Decision

1. **Dedicated Service Account for Cloud Run**:
   - `portfolio-copilot-frontend-sa@${PROJECT_ID}.iam.gserviceaccount.com`:
     - Granted `roles/datastore.user` (Firestore) for reading holdings and appending to audit log.
     - Granted `roles/bigquery.dataViewer` for fan-out chart queries.
     - **No Secret Manager access** (Alpaca key access is strictly confined to the orchestrator).
   - `orchestrator` is deployed exclusively via Agent Runtime ([ADR-0008](0008-python-for-orchestrator.md)).

2. **Agent Identity for Agent Runtime (`orchestrator`)**:
   - Deployed with `identity_type=AGENT_IDENTITY` (SPIFFE-based per-agent cryptographic identity tied to the agent's lifecycle).
   - Bound to least-privilege IAM roles:
     - `roles/datastore.user` (Firestore: IPS, holdings, liabilities)
     - `roles/bigquery.dataViewer` (BigQuery: spending analysis)
     - `roles/secretmanager.secretAccessor` (Secret Manager: Alpaca API key)
   - Agent Platform Service Agent (`service-${PROJECT_NUMBER}@gcp-sa-aiplatform.iam.gserviceaccount.com`) is granted `roles/secretmanager.secretAccessor` for deployment-time secret resolution.

## Consequences
- **Security**: No service runs with default or over-permissioned credentials. Compromising the frontend web container does not expose Alpaca secrets or execution credentials.
- **Auditability**: Cloud Logging and IAM policies explicitly track agent operations under the strongly attested SPIFFE identity.
- **Clean Separation**: Frontend web host and Orchestrator responsibilities and permissions remain cleanly segregated.
