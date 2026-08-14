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
- Server uses `store.Store` and `bigquery.Runner` interfaces for dependency injection and testability.
- Defined a document-type contract with strict extension and schema validation:
  - `transactions` (CSV): validated for exact 6-column header names and canonical order (`user_id,transaction_date,amount,description,raw_category,normalized_category`), ISO date format, valid amounts, and non-empty categories. Rows are strictly scoped to the request `user_id` and streamed into BigQuery (`portfolio_copilot.<target_table>`) via `BigQueryRunner.InsertTransactions`. If BigQuery client is uninitialized, returns explicit `503 Service Unavailable`.
  - Streaming ingestion generates deterministic row `insertID`s (SHA-256 hash of row fields) using `bigquery.StructSaver` to enable BigQuery's built-in 1-minute streaming deduplication against accidental re-uploads.
  - `holdings` (JSON): validated against `holdings.schema.json`, request `user_id` enforced over any body payload to prevent IDOR/cross-tenant overwrite, and saved to `holdings/{user_id}`.
  - `liabilities` (JSON): validated against `liabilities.schema.json`, request `user_id` enforced, and saved to `liabilities/{user_id}`.
  - `ips` (JSON): validated against `ips.schema.json`, request `user_id` enforced, and updated in `ips/{ips_id}_v{version}`.
- Added `UserID` and `DocumentType` to `contracts.DocumentItem` and scoped `GetDocuments` query via `.Where("user_id", "==", userID)` to prevent cross-tenant document metadata leakage.
- Added `SetDocument` to `pkg/store/crud.go` and `Store` interface, recording `contracts.DocumentItem` audit metadata into Firestore collection `documents`.
- When storage backends are uninitialized / nil, endpoints return honest `503 Service Unavailable` or `HasActiveIPS: false` rather than reporting synthetic success.
- Re-enabled `DocumentsView.vue` with `UploadDropzone.vue` type selector and live Ingested Documents History table.

## Consequences
- Single-click review and update of investment policies without losing prior versions.
- Full end-to-end data ingestion pipeline supporting bank CSVs directly into BigQuery (with streaming deduplication) and financial snapshot JSONs into Firestore with complete IDOR protection and user scoping.
- All 110 Vue unit tests, Go tests, and 351 Python tests remain green.
