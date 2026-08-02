# ADR-0011: Scoped Service Accounts for Cloud Run and Agent Identity for Agent Runtime

## Status
Accepted

## Context
Initial infrastructure scaffolding deployed Cloud Run services under default compute service accounts and provisioned Agent Runtime (Agent Engine) without identity configuration. This violates the principle of least privilege.

Different components in the Portfolio Copilot architecture have distinct operational scopes and resource access requirements:
- **Gateway (Go on Cloud Run)**: Directly handles user authentication, session tokens, audit logging to Firestore, and fan-out queries to BigQuery for charts ([ADR-0003](0003-standalone-ui-not-agentspace.md)). It does not execute trades or call Alpaca directly ([ADR-0005](0005-managed-agents-hybrid-evaluation.md)).
- **Frontend (Vue/TS on Cloud Run)**: Pure UI client that talks exclusively to the Gateway API; it never interacts directly with GCP APIs or databases.
- **Orchestrator (Python on Agent Runtime)**: Executes planner logic, coordinates skills, accesses Firestore for IPS and holdings, BigQuery for spending analysis, and Alpaca API credentials from Secret Manager.

## Decision

1. **Dedicated Service Accounts for Cloud Run**:
   - `portfolio-copilot-gateway-sa@${PROJECT_ID}.iam.gserviceaccount.com`:
     - Granted `roles/datastore.user` (Firestore) for reading holdings and appending to audit log.
     - Granted `roles/bigquery.dataViewer` for fan-out chart queries.
     - **No Secret Manager access** (Alpaca key access is strictly confined to the orchestrator).
   - `portfolio-copilot-frontend-sa@${PROJECT_ID}.iam.gserviceaccount.com`:
     - **Zero additional IAM bindings** beyond default (calls Gateway API only).
   - `orchestrator` is removed from Cloud Run deployment scripts, as it deploys exclusively via Agent Runtime ([ADR-0008](0008-python-for-orchestrator.md)).

2. **Agent Identity for Agent Runtime (`orchestrator`)**:
   - Deployed with `identity_type=AGENT_IDENTITY` (SPIFFE-based per-agent cryptographic identity tied to the agent's lifecycle).
   - Bound to least-privilege IAM roles:
     - `roles/datastore.user` (Firestore: IPS, holdings, liabilities)
     - `roles/bigquery.dataViewer` (BigQuery: spending analysis)
     - `roles/secretmanager.secretAccessor` (Secret Manager: Alpaca API key)
   - Agent Platform Service Agent (`service-${PROJECT_NUMBER}@gcp-sa-aiplatform.iam.gserviceaccount.com`) is granted `roles/secretmanager.secretAccessor` for deployment-time secret resolution.

## Consequences
- **Security**: No service runs with default or over-permissioned credentials. Compromising one component (e.g. gateway or frontend) does not expose Alpaca secrets or execution credentials.
- **Auditability**: Cloud Logging and IAM policies explicitly track agent operations under the strongly attested SPIFFE identity.
- **Clean Separation**: Gateway and Orchestrator responsibilities and permissions remain cleanly segregated.
