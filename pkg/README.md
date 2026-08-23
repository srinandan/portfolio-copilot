# Go Shared Packages (`pkg/`)

This directory contains the shared Go packages for **Portfolio Copilot**, consumed by the Go backend host and API server (`frontend/server/`).

These packages implement the transactional Firestore repository, analytical BigQuery query runner and streaming inserter, and typed Go contracts aligned with the project's canonical JSON schemas.

---

## Package Overview

```
pkg/
├── contracts/          # Go data models matching /schemas JSON schemas & TS types
│   ├── audit_log.go        # AuditLogEntry, event types, actors
│   ├── holdings.go         # HoldingsSnapshot, Position, AccountType
│   ├── ips.go              # InvestmentPolicyStatement, TargetAllocation, Constraints
│   ├── liabilities.go     # LiabilitiesSnapshot, LiabilityItem
│   ├── profile.go          # UserProfile, FamilyDependent, OnboardingProfile
│   ├── proposed_action.go  # ProposedAction, ActionType, ActionSide, ActionStatus
│   ├── reports.go          # DriftReport, SpendingReport, DocumentItem
│   ├── reviewer_verdict.go # ReviewerVerdict, RuleResult, RuleStatus
│   └── w2.go               # W2Document, W2Wages, W2Box12Item, W2Employer/Employee
├── documentai/         # Form W-2 parsing via Google Cloud Document AI (+ offline mock)
│   ├── parser.go           # Parser interface, SSN masking, currency/tax-year helpers
│   ├── gcp.go              # GCPW2Parser: US W-2 processor client + entity normalization
│   └── mock.go             # MockW2Parser: deterministic offline parser for dev/tests
├── store/              # Firestore data client, transactional CRUD, and read operations
│   ├── client.go           # Store interface and Firestore client initialization
│   ├── crud.go             # Transactional mutations (SetHoldings, UpdateIPS, SetUserProfile, SetW2Document, etc.)
│   └── reads.go            # Queries (GetHoldings, GetActiveIPS, GetUserProfile, GetW2Documents, etc.)
└── bigquery/           # BigQuery transaction runner and streaming inserter
    ├── bigquery.go         # Runner interface, SQL sandboxing with user-scoped CTE wrapping
    └── bigquery_client.go  # Live BigQuery client and streaming transaction insertion (StructSaver)
```

---

## 1. `pkg/contracts`

Typed Go struct definitions matching the project's canonical JSON schemas under [`/schemas`](../schemas) and TypeScript definitions under [`frontend/src/types`](../frontend/src/types).

- **`contracts.UserProfile`**: Captures demographic, employment, family dependents, retirement timeline, and freeform goal notes.
- **`contracts.InvestmentPolicyStatement`**: Append-only reference plan defining asset allocation bands, risk tolerance, and trading constraints.
- **`contracts.LiabilitiesSnapshot`**: Current debt obligations, APRs, and minimum monthly payments.
- **`contracts.HoldingsSnapshot`**: Current portfolio positions, cash balance, and total valuation.
- **`contracts.ProposedAction`**: Specific proposed trades drafted by the orchestrator.
- **`contracts.ReviewerVerdict`**: Itemized policy compliance and risk evaluations.
- **`contracts.AuditLogEntry`**: Immutable governance ledger events with skill versions and approval scopes.
- **`contracts.DocumentItem`**: Audit metadata for user-uploaded statement documents.
- **`contracts.W2Document`**: Parsed IRS Form W-2 (wages, withholdings, Box 12 codes, state/local taxes) with the employee SSN stored masked.
- **`contracts.OnboardingProfile`**: Unified payload used by `/api/onboarding` and `/api/profile` to view and update user policy settings.

Schema synchronization is verified in CI via [`scripts/sync-schemas.sh`](../scripts/sync-schemas.sh).

---

## 2. `pkg/store`

Firestore repository implementing transactional persistence and queries against Google Cloud Firestore.

### Key Operations
- **`Store` Interface**:
  - **Holdings**: `GetHoldings(ctx, userID)`, `SetHoldings(ctx, holdings)`
  - **IPS**: `GetActiveIPS(ctx, userID)`, `UpdateIPS(ctx, ips)` (enforces append-only versioning and supersedes previous versions atomically)
  - **Liabilities**: `GetLiabilities(ctx, userID)`, `SetLiabilities(ctx, liabilities)`
  - **User Profile**: `GetUserProfile(ctx, userID)`, `SetUserProfile(ctx, profile)`
  - **Documents**: `GetDocuments(ctx, userID)`, `SetDocument(ctx, doc)`
  - **W-2 Documents**: `GetW2Documents(ctx, userID)`, `GetW2Document(ctx, userID, docID)`, `SetW2Document(ctx, doc)`, `DeleteW2Document(ctx, userID, docID)` (owner-scoped; cross-user access returns NotFound)
  - **Audit Log**: `GetAuditLogs(ctx, userID, limit)`, `WriteAuditLog(ctx, entry)`
  - **Reports**: `GetSpendingReport(ctx, userID)`, `GetDriftReport(ctx, userID)`

---

## 3. `pkg/bigquery`

Manages analytical transaction queries and streaming ingestion against Google Cloud BigQuery (`portfolio_copilot.checking_transactions`).

### Key Capabilities
- **SQL Sandboxing**: `bigquery.WrapUserScopedQuery` ensures queries only execute `SELECT` statements, reject destructive/scripting keywords (`MERGE`, `EXECUTE`, `LOAD`, etc.), and wrap all references in a Common Table Expression (CTE) scoping rows strictly to the authenticated `user_id`.
- **Streaming Ingestion**: `bigquery.InsertTransactions` streams CSV transaction rows directly into BigQuery using `bigquery.StructSaver` with deterministic SHA-256 insert IDs for 1-minute streaming deduplication.

---

## 4. `pkg/documentai`

Parses uploaded IRS Form W-2 income statements. Defines the `Parser` interface with two implementations, selected at startup based on configuration:

- **`GCPW2Parser`**: Calls the Google Cloud Document AI pre-trained US W-2 processor and normalizes the extracted entities into a `contracts.W2Document`.
- **`MockW2Parser`**: A deterministic offline parser used for local development and CI when `DOCUMENT_AI_PROCESSOR_ID` is unset.

Employee SSNs are masked in-memory (`***-**-XXXX`) before the document is persisted or returned in an API response. See [ADR-0026](../docs/adr/0026-w2-document-ai-ingestion-and-profile-sync.md).

---

## Testing

Run tests across all Go packages:

```bash
go test ./pkg/... -cover
```
