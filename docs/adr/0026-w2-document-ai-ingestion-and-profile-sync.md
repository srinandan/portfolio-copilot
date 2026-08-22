# ADR-0026: IRS Form W-2 Ingestion via GCP Document AI & Profile Synchronization

## Status

Accepted

## Context

Portfolio Copilot users currently ingest checking account transactions into BigQuery (`portfolio_copilot.checking_transactions`) and account balances/liabilities/IPS snapshots into Firestore. However, calculating accurate savings capacity, debt-to-income limits, and retirement contributions requires verified income and tax data.

IRS Form W-2 (Wage and Tax Statement) contains authoritative records of gross compensation (Box 1), federal/state income tax withholdings (Boxes 2, 17), FICA contributions (Boxes 4, 6), elective retirement deferrals (Box 12 codes such as `D` for 401(k)), and employer information. Users need a streamlined mechanism in the Profile Hub to upload W-2 documents (PDF, PNG, JPEG), parse them with high fidelity, review the extracted values, and synchronize their verified income into their user profile.

## Decision

### 1. Extraction Engine: Pre-trained GCP Document AI W-2 Processor
- Utilize Google Cloud's specialized **US W-2 Tax Processor** (`FORM_W2_PROCESSOR` / `w2-parser`) via `cloud.google.com/go/documentai/apiv1`.
- Avoid brittle custom OCR heuristics or unconstrained general LLM vision prompts for structured tax forms: Document AI provides canonical entity extraction, normalized currency values, and confidence scores across IRS form layouts.
- Configuration is parameterized via environment variables: `DOCUMENT_AI_PROJECT_ID`, `DOCUMENT_AI_LOCATION` (default `us`), and `DOCUMENT_AI_PROCESSOR_ID`.

### 2. Hermetic Offline Mocking for Development & CI
- Introduce a `documentai.Parser` interface in `pkg/documentai/parser.go` with two implementations:
  1. `GCPW2Parser`: Calls the live GCP Document AI API when configured.
  2. `MockW2Parser`: A deterministic offline parser equipped with standard IRS W-2 test fixtures that normalizes test files, computes entity confidence, and runs hermetically during local development and automated CI runs without requiring cloud credentials.

### 3. Dedicated Firestore Storage & Schema Validation
- Parsed W-2 statements are stored in a dedicated top-level collection **`w2_documents`** (`w2_documents/{doc_id}`).
- All writes are validated against canonical JSON schema `schemas/w2-document.schema.json` ensuring required fields (`user_id`, `tax_year`, `wages_and_compensation`, `status`, `uploaded_at`).
- Ingestion events simultaneously record an audit entry in the `documents` metadata collection (`contracts.DocumentItem`).

### 4. PII Security & SSN Masking
- In accordance with least-privilege and sensitive data security, employee Social Security Numbers (SSN) are masked in memory (`***-**-XXXX` preserving only the last 4 digits) immediately upon entity extraction.
- Unmasked SSNs are never persisted to Firestore or emitted in HTTP responses.

### 5. Explicit 1-Click Profile Synchronization
- Document AI extraction does not silently overwrite the user's primary profile.
- Instead, the extracted values are presented to the user in the UI with an explicit **"Apply to Profile Income"** action (`POST /api/profile/w2/:id/apply`), allowing the user to inspect the extracted Box 1 wages and employer before updating `UserProfile.annual_income_usd` and `occupation` in `user_profiles/{user_id}`.

### 6. Profile Hub UI Integration
- Add a dedicated 6th tab **"Income & Tax"** (`id: 'income'`, icon `receipt_long`) to `ProfileView.vue`.
- Features an interactive dropzone supporting PDF, PNG, and JPEG uploads up to 10MB, tax year summary cards, detailed Box 1–20 breakdowns (Federal, FICA, Box 12 elective benefits, State/Local taxes), and audit metadata.

### 7. Runtime Agent Skill Consumption
- Update `skills/goals-onboarding/SKILL.md` to accept `w2_documents` as an optional input source and declare `read:w2` approval scope, enabling the agent planner to reference verified income and Box 12 retirement deferrals during goal feasibility assessments.

## Consequences

- **Positive:** High-fidelity, automated tax document ingestion backed by GCP Document AI without risking prompt hallucinations.
- **Positive:** Hermetic development and testing workflows via `MockW2Parser`.
- **Positive:** Strong privacy and PII protection via in-memory SSN masking.
- **Positive:** Predictable user control over financial metrics through explicit 1-click profile synchronization.
- **Neutral:** Requires `documentai.googleapis.com` API enablement and a configured `FORM_W2_PROCESSOR` processor ID for production deployments.
