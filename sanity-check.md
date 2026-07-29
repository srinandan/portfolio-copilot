# Sanity Check: F1–F4 — Findings & Fix Instructions

Reviewed by cloning `srinandan/portfolio-copilot` at current `main`
(commit `2386063`) and reading the actual merged code — not just the
PR titles. One critical issue, two real bugs, and some structural debt
worth clearing before F5 builds on top of this.

**Caveat up front:** this review has no Go toolchain available to it —
everything below is from reading source, git history, and CI config
directly, not from running `go build`/`go test`. **Priority 0's first
step is to actually run the build and full test suite** before touching
anything else, since the deleted files below may currently make
`orchestrator` fail to build outright.

---

## Priority 0 (blocking): F3 and F4 source code is missing from `main`

PRs #33 (Agent Registry client) and #34 (BigQuery) both show as merged.
**Their actual source files are not on `main`.** They were deleted as a
side effect of how PR #35 (the Firestore/`pkg/store` branch) resolved a
merge conflict when catching up with `main`.

### The trail

- `1310bf2` — Agent Registry client implemented (`orchestrator/registry/client.go`, 222 lines + 250-line test file)
- `93dd923` — merged to `main` via PR #33
- `69e37b1` — BigQuery schema + query execution implemented (`orchestrator/data/bigquery.go`, `bigquery_client.go`, plus tests, plus `infra/setup_bigquery.sh`)
- `479a17f` — merged to `main` via PR #34
- `1529060` — the Firestore branch merges `main` into itself to catch up
- **`0ab93fa`** — while finalizing that merge, deletes `orchestrator/registry/client.go`, `orchestrator/registry/client_test.go`, `orchestrator/data/bigquery.go`, `orchestrator/data/bigquery_client.go`, `orchestrator/data/bigquery_client_test.go`, `orchestrator/data/bigquery_test.go`, and `infra/setup_bigquery.sh` — 773 lines total, silently, as part of a conflict resolution that should have kept both sides
- `2386063` — this state merges to `main` via PR #35 and is the current tip

Confirmed via `git merge-base --is-ancestor` that both `1310bf2` and
`69e37b1` are real ancestors of current `HEAD` — this isn't an
abandoned branch, the good code genuinely existed on `main` and was
removed.

### Fix

Restore the files verbatim from history, then re-verify they still
build against whatever `go.mod`/dependency changes happened since:

```bash
git show 1310bf2:orchestrator/registry/client.go      > orchestrator/registry/client.go
git show 1310bf2:orchestrator/registry/client_test.go > orchestrator/registry/client_test.go

git show 69e37b1:orchestrator/data/bigquery.go             > orchestrator/data/bigquery.go
git show 69e37b1:orchestrator/data/bigquery_client.go      > orchestrator/data/bigquery_client.go
git show 69e37b1:orchestrator/data/bigquery_client_test.go > orchestrator/data/bigquery_client_test.go
git show 69e37b1:orchestrator/data/bigquery_test.go        > orchestrator/data/bigquery_test.go
git show 69e37b1:infra/setup_bigquery.sh                   > infra/setup_bigquery.sh
```

After restoring:
1. `go build ./...` and `go vet ./...` in `orchestrator/` — the restored
   files may need `go.mod`/`go.sum` entries re-added, since the deletion
   commit also touched `orchestrator/go.mod` (57 lines removed) and
   `orchestrator/go.sum` (204 lines removed)
2. `go test ./...` — confirm the restored test suites actually pass, not
   just that the files exist
3. Don't just re-merge blindly — read the restored files against what's
   now in `orchestrator/contracts/` and `pkg/store/`, in case anything
   genuinely needs reconciling (e.g. the registry client should use the
   same `contracts` types the rest of the codebase settled on)

**This blocks F5** — the root planner issue explicitly depends on F4's
registry client existing. Don't start F5 until this is resolved and
verified building/passing.

---

## Priority 1: Real bugs (not style)

### 1. Firestore documents don't use the documented schema field names

None of the contract types (`orchestrator/contracts/*.go`) have
`firestore:"..."` struct tags — only `json:"..."`. The Firestore Go SDK
does **not** read `json` tags; without an explicit `firestore` tag it
falls back to the literal Go field name. So documents are actually
being persisted with fields like `IPSID`, `TargetAllocation`,
`RiskTolerance` — not the `ips_id`, `target_allocation`,
`risk_tolerance` documented in `schemas/*.schema.json` and
`docs/spec/03-contracts.md`.

This also means the schema-validation step in `pkg/store/client.go`
(`validate()`, which uses `json.Marshal` — correctly respecting `json`
tags) is validating a **different serialization** than what
`tx.Set(docRef, data)` actually persists (which uses Firestore's own
struct-to-map conversion, ignoring `json` tags entirely). Validation
currently doesn't protect what actually gets written.

**Fix:** add `firestore:"snake_case_name"` tags matching every existing
`json` tag, on every contract type in `orchestrator/contracts/`. Example:

```go
IPSID  string `json:"ips_id" firestore:"ips_id"`
UserID string `json:"user_id" firestore:"user_id"`
```

Then update `pkg/store/crud.go`'s Firestore queries (`Where("IPSID", ...)`,
`Where("Status", ...)` in `UpdateIPS`) to use the new snake_case field
names to match.

**Acceptance criteria:** write an IPS via `UpdateIPS`, then read the raw
document back from the Firestore emulator (bypassing the Go struct) and
confirm its field names match `schemas/ips.schema.json` exactly —
`ips_id`, not `IPSID`.

### 2. IPS validation doesn't check band ordering

`InvestmentPolicyStatement.Validate()` checks each of
`target_percent`/`min_percent`/`max_percent` is within `[0, 100]`
individually, but never checks `min_percent <= target_percent <=
max_percent`. A document like `{target: 60, min: 70, max: 50}` currently
passes validation. Portfolio Analysis (when it's built) will assume that
ordering holds — it has no reason to re-check it.

**Fix:** add to `AllocationBand` validation (or a method on it):
```go
if allocation.MinPercent > allocation.TargetPercent || allocation.TargetPercent > allocation.MaxPercent {
    return false
}
```

**Acceptance criteria:** a test case with `min > target` or `target >
max` fails validation; the existing valid fixtures still pass.

---

## Priority 2: CI doesn't actually verify what it claims to

### 3. `pkg/store` isn't in the CI test matrix at all

`.github/workflows/ci.yml`'s `go` job matrix is `[orchestrator,
gateway]`. `pkg/store` was added as its own Go module (see Priority 3
below) and was never added to this list — its tests have never run in
CI, not even once, on any PR.

**Fix:** add `pkg/store` to the matrix in `ci.yml`:
```yaml
matrix:
  module: [orchestrator, gateway, pkg/store]
```

### 4. Even if added to the matrix, the emulator-dependent tests would just skip

`pkg/store/crud_test.go`'s `setupTestClient` does:
```go
if os.Getenv("FIRESTORE_EMULATOR_HOST") == "" {
    t.Skip("Skipping test: FIRESTORE_EMULATOR_HOST not set")
}
```

No CI workflow sets this variable or runs a Firestore emulator service.
This means `TestUpdateIPSTransaction` — the test covering the single
most safety-critical property in the entire data layer, the versioning
invariant — has **never actually executed** in CI. It's been silently
skipped on every run, and CI still reports green.

**Fix:** add a Firestore emulator service/step to the `pkg/store` CI job
before the test step, e.g.:
```yaml
- name: Start Firestore emulator
  run: |
    gcloud emulators firestore start --host-port=localhost:8080 &
    sleep 5
  # requires gcloud CLI on the runner, or use a docker service container
  # running gcr.io/google.com/cloudsdktool/cloud-sdk with the emulator
- name: Test with coverage
  env:
    FIRESTORE_EMULATOR_HOST: localhost:8080
  run: go test ./... -coverprofile=coverage.out
```

**Acceptance criteria:** `TestUpdateIPSTransaction` shows as **passed**,
not skipped, in a real CI run's log output.

---

## Priority 2: Structural debt worth clearing now, before F5 adds more surface area

### 5. Three Go modules, no `go.work`, one is empty and inert

Current state:
- root `go.mod` (module `portfolio-copilot`) — has `replace` directives
  for `pkg/store` and `orchestrator`, but **no `require` block at all**,
  so those replaces do nothing. No `.go` files live at the repo root.
  This module currently does nothing.
- `orchestrator/go.mod` (module `orchestrator`) — separate module, zero
  external dependencies currently
- `pkg/store/go.mod` (module `portfolio-copilot/pkg/store`) — separate
  module, requires `orchestrator` via a local `replace`

No `go.work` file ties these together. This is more fragmentation than
the project needs at this stage — per this repo's own
`.agent/skills/concise-code/SKILL.md`: *"Prefer the straightforward
implementation... don't introduce an interface, abstraction layer...
until there are at least two concrete cases that need it."* Three module
boundaries before F5 (which will need to import both `contracts` and
`store`) even exists is exactly that pattern.

**Recommended fix:** consolidate to a single Go module at the repo root
(`module portfolio-copilot`), with `orchestrator/`, `pkg/store/` (and
later `gateway/`) as plain packages under it, not separate modules. Drop
the now-redundant `orchestrator/go.mod` and `pkg/store/go.mod`; move
their dependencies into one root `go.mod`/`go.sum`. Import paths become
`portfolio-copilot/orchestrator/contracts`,
`portfolio-copilot/pkg/store`, etc.

If there's a specific reason multiple modules are wanted (independent
versioning, separate release cadence) that isn't apparent from the repo
as it stands — flag that back rather than assuming this
recommendation is right, since it's a real tradeoff, not a clear bug.

### 6. `pkg/store/schemas/*.schema.json` is a duplicate of `/schemas/*.schema.json`

`go:embed` can only embed files at-or-below the directory of the source
file doing the embedding — it can't reach `../../schemas` from
`pkg/store/client.go`. That's *why* the copy exists, not a mistake, but
as committed right now there's nothing stopping the two copies from
silently drifting (someone updates `schemas/ips.schema.json` for a new
field and forgets `pkg/store/schemas/ips.schema.json` exists).

**Fix:** treat `pkg/store/schemas/` as a generated artifact, not a
second source of truth:
- Add a header comment to each file in `pkg/store/schemas/`:
  `// GENERATED — copied from /schemas. Run scripts/sync-schemas.sh, do not edit directly.`
- Add `scripts/sync-schemas.sh` that copies `/schemas/*.json` into
  `pkg/store/schemas/`
- Add a CI check (or a step in the `pkg/store` test job) that runs a
  `diff` between the two directories and fails if they don't match

---

## Priority 3: Worth a decision, not urgent

### 7. OSV-Scanner was disabled, not fixed

Commit `03afa3c` changed `osv-scanner.yml`'s triggers from
`pull_request`/`push`/`schedule` to `workflow_dispatch` only — meaning
it no longer runs automatically at all. The commits right before it
(`chore(deps): update golang.org/x/crypto...`, `...update remaining
dependencies to fix osv-scanner warnings`) suggest it was fighting
dependency-vulnerability findings and got turned off instead of the
underlying findings being resolved.

Given this project's whole premise is agent governance, silencing a
security scanner rather than resolving what it flagged is worth a
deliberate decision, not something to leave as a side effect of a CI
frustration. Not blocking F5 — just shouldn't be forgotten.

---

## Summary for whoever picks this up

1. **Do this first, before anything else:** restore the seven deleted
   files (Priority 0), confirm `go build ./...` and `go test ./...` pass
   across all modules
2. Fix the two real bugs (Firestore field-name tags, band-ordering
   validation) — Priority 1
3. Fix CI to actually run `pkg/store`'s tests against a real emulator —
   Priority 2 (#3/#4)
4. Consider the module-consolidation and schema-duplication cleanup
   before F5 adds more code on top of the current structure — Priority 2
   (#5/#6)
5. Decide what to do about OSV-Scanner — Priority 3

Once 1–3 are done and verified, F5 (root planner) is safe to start.

