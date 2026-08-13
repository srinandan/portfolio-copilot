# ADR-0020: Typed Document Ingestion & Onboarding Profile View/Edit

## Status
Accepted

## Context
Two key usability gaps existed in Portfolio Copilot:
1. **Onboarding Read Gap**: The onboarding wizard collected and saved the user's investment goals, risk calibration, target asset allocation bands, constraints, liabilities, and approval thresholds into Firestore (`ips/{ips_id}_v{version}` and `liabilities/{user_id}`). However, reopening `/onboarding` always defaulted to hard-coded sample state, preventing users from reviewing or updating their reference plan.
2. **Document Ingestion Placeholder**: The `/documents` view was previously an inert placeholder awaiting a real ingestion handler and database writer. Users needed a typed upload mechanism to ingest transactions (CSV into BigQuery) and holdings, liabilities, or IPS balance snapshots (JSON into Firestore) with strict schema validation and persistent audit metadata (`DocumentItem`).

## Decision

### 1. Onboarding Profile Read Endpoint & Edit Lifecycle
- Added `GET /api/onboarding` on the Go frontend server (`frontend/server/handlers.go`).
- Added `GetLiabilities` to `pkg/store/reads.go` and the `Store` interface.
- Unified response model `contracts.OnboardingProfile` carries active IPS metadata, goals, target bands, liquidity needs, policy guardrails, approval thresholds, and debt liabilities.
- `OnboardingView.vue` queries `apiService.getOnboarding()` on mount. When an active IPS exists (`has_active_ips: true`), the wizard prefills with stored state and displays an active profile banner.
- On saving changes from an existing profile, the request forwards `trigger: 'update'`, creating a new active IPS version that supersedes the prior one according to the append-only invariant.

### 2. Typed Document Ingestion Endpoint & Validation
- Added `POST /api/documents` (multipart/form-data) in `frontend/server/handlers.go`.
- Defined a document-type contract with strict extension and schema validation:
  - `transactions` (CSV): validated for header and record counts, targeted at `checking_transactions` or `chase_transactions`.
  - `holdings` (JSON): validated against `holdings.schema.json` and saved to `holdings/{user_id}`.
  - `liabilities` (JSON): validated against `liabilities.schema.json` and saved to `liabilities/{user_id}`.
  - `ips` (JSON): validated against `ips.schema.json` and updated in `ips/{ips_id}_v{version}`.
- Added `SetDocument` to `pkg/store/crud.go` and `Store` interface, recording `contracts.DocumentItem` metadata (ID, filename, type, target, size, timestamp, status, and parsed record count) into Firestore collection `documents`.
- Re-enabled `DocumentsView.vue` with `UploadDropzone.vue` type selector and live Ingested Documents History table.

## Consequences
- Single-click review and update of investment policies without losing prior versions.
- Full end-to-end data ingestion pipeline supporting bank CSVs and financial snapshot JSONs without synthetic mocks.
- All 110 Vue unit tests, Go tests, and 351 Python tests remain green.
