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
│   └── reviewer_verdict.go # ReviewerVerdict, RuleResult, RuleStatus
├── store/              # Firestore data client, transactional CRUD, and read operations
│   ├── client.go           # Store interface and Firestore client initialization
│   ├── crud.go             # Transactional mutations (SetHoldings, UpdateIPS, SetUserProfile, etc.)
│   └── reads.go            # Queries (GetHoldings, GetActiveIPS, GetUserProfile, GetDocuments, etc.)
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
  - **Audit Log**: `GetAuditLogs(ctx, userID, limit)`, `WriteAuditLog(ctx, entry)`
  - **Reports**: `GetSpendingReport(ctx, userID)`, `GetDriftReport(ctx, userID)`

---

## 3. `pkg/bigquery`

Manages analytical transaction queries and streaming ingestion against Google Cloud BigQuery (`portfolio_copilot.chase_transactions` / `checking_transactions`).

### Key Capabilities
- **SQL Sandboxing**: `bigquery.WrapUserScopedQuery` ensures queries only execute `SELECT` statements, reject destructive/scripting keywords (`MERGE`, `EXECUTE`, `LOAD`, etc.), and wrap all references in a Common Table Expression (CTE) scoping rows strictly to the authenticated `user_id`.
- **Streaming Ingestion**: `bigquery.InsertTransactions` streams CSV transaction rows directly into BigQuery using `bigquery.StructSaver` with deterministic SHA-256 insert IDs for 1-minute streaming deduplication.

---

## Testing

Run tests across all Go packages:

```bash
go test ./pkg/... -cover
```
