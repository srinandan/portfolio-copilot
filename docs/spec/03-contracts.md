# Shared Contracts

These are the data shapes every skill, the orchestrator, the
Reviewer/Critic, and the frontend must agree on. They're documented here
— before any per-skill requirements or implementation issues — specifically
so that agents working different issues in parallel converge on the same
shapes instead of each inventing their own.

The JSON Schema files under [`/schemas`](../../schemas) are the actual
source of truth (used to validate payloads and generate Go structs / TS
types). This document explains the *why* behind each field and how the
contracts relate to each other — read it before writing code against
them.

**Note on completeness:** this list has grown as gaps got caught —
`HoldingsSnapshot` and `LiabilitiesSnapshot` were added after being
referenced informally elsewhere in the docs without ever being
formalized. If you find a data shape multiple components depend on that
isn't listed here, that's a signal to add it, not to invent a local
shape.

## How they relate

```
HoldingsSnapshot          LiabilitiesSnapshot
(current state)            (current state)
        │                          │
        └──────────┬───────────────┘
                    │ read by
                    ▼
          Goals & Onboarding
                    │
                    ▼
  Investment Policy Statement (IPS)  ◄──────────────┐
        │                                            │
        │ read by (IPS + Holdings)                   │ read by
        ▼                                            │
Portfolio Analysis ── drift ──► Action Drafting       │
                                       │               │
                                       ▼               │
                              Proposed Action ─────────┘
                                       │
                                       ▼
                              Reviewer/Critic
                                       │
                                       ▼
                              Reviewer Verdict
                                       │
                              (if requires_human_approval)
                                       ▼
                              Human approval gate
                                       │
                                       ▼
                                  Execution

Every step above that changes state → Audit Log Entry
```

## 1. Holdings Snapshot

Current portfolio positions. **Current-state, not versioned** — unlike
the IPS, this gets overwritten as holdings change rather than
superseded. Read by Goals & Onboarding (feasibility-checking goals
against what's actually there) and Portfolio Analysis (drift
calculation).

`asset_class` on each position must match one of the IPS's
`target_allocation` asset classes, or drift comparison has nothing to
compare against.

See [`holdings.schema.json`](../../schemas/holdings.schema.json).

## 2. Liabilities Snapshot

Current debts — credit cards, mortgage, other loans. **Also
current-state, not versioned.** Added after being referenced informally
(risk tolerance, liquidity needs) without ever being captured anywhere:
neither the IPS schema nor the Goals & Onboarding interview asked about
what a user owes, only what they hold and want.

This is deliberately **not derived from checking transaction data** — a
transaction feed shows payments happening, not the interest rate or
outstanding balance behind them. It has to be self-reported during the
Goals & Onboarding interview.

`interest_rate_percent` exists specifically so a future Reviewer rule
could reasonably flag "you're carrying 22% APR debt while proposing to
buy more equity" — not built yet, but the field is there because this is
exactly the kind of thing a real risk-capacity assessment (as opposed to
risk *tolerance*) should account for.

See [`liabilities.schema.json`](../../schemas/liabilities.schema.json).

## 3. Investment Policy Statement (IPS)

The reference plan. Produced once by Goals & Onboarding, revisited on
drift or major life events. **Append-only, like the ADRs** — a change to
goals or risk tolerance creates a new IPS version; the old one is marked
`superseded`, never edited in place. This matters for audit: a Reviewer
decision needs to be checkable against the exact IPS version that was
active when it ran, not whatever the IPS looks like today.

Notable fields:
- `target_allocation` uses **bands** (`min_percent`/`max_percent` around
  a target), not a single point value — this is standard IPS practice and
  is what lets Portfolio Analysis distinguish "drifted, needs attention"
  from "within tolerance."
- `approval_required_above_usd` / `approval_required_above_percent` —
  the IPS itself defines what counts as "high-stakes" for this user. This
  is what the root planner's judgment call ("should this go to a human?")
  actually checks against, rather than being a vague heuristic.
- `excluded_tickers` / `excluded_sectors` and `concentration_limit_percent`
  are the fields the Reviewer's exclusion and concentration rules read
  directly.

See [`ips.schema.json`](../../schemas/ips.schema.json).

## 4. Proposed Action

What Action Drafting produces, what the Reviewer validates, and what a
human ultimately approves or rejects. Deliberately narrow in this version
(`type` is only ever `"trade"`) — extend the enum later if a second action
type is actually needed, don't pre-build for one that isn't.

Notable fields:
- `ips_version_referenced` — every proposed action is checked against a
  specific IPS version. If the IPS changes between drafting and review,
  the Reviewer's stale-version rule (see below) catches it.
- `proposed_by_skill_version` — governance traceability: which skill,
  which version, drafted this.
- `rationale` and `supporting_research_refs` exist for two audiences:
  the human deciding whether to approve, and anyone auditing the decision
  later.

See [`proposed-action.schema.json`](../../schemas/proposed-action.schema.json).

## 5. Reviewer Verdict

The Reviewer/Critic's output. **Itemized, not a single pass/fail** —
`rule_results` lists every rule checked, each with its own pass/fail and
detail. This is deliberate: the adversarial-test demo scenario depends on
being able to point at exactly which rule caught a manipulated proposal,
not just assert that "the system worked."

Baseline rules the Reviewer is expected to check (implementation detail,
not part of the schema itself):
- Ticker not in `excluded_tickers`/`excluded_sectors`
- Resulting position doesn't exceed `concentration_limit_percent`
- Trade moves allocation toward, not away from, the `target_allocation`
  band
- Order value isn't absurd relative to portfolio size (the specific check
  that should catch a poisoned-tool-result attempt at an oversized trade)
- `ips_version_referenced` matches the currently active IPS version

`requires_human_approval` can be `true` even when every rule passes — an
action can be policy-compliant and still be high-stakes enough (per the
IPS's own thresholds) to need a human.

See [`reviewer-verdict.schema.json`](../../schemas/reviewer-verdict.schema.json).

## 6. Audit Log Entry

One entry per governance-relevant event — not just approvals. Emitted for
proposals drafted, reviews completed, approvals granted/rejected,
executions, and skill revocations. Every entry carries `skill_name` +
`skill_version` + `registry_entry_id` + `approval_scope` where applicable —
this is what makes the "traceable to skill version, registry entry, and
approval scope" claim in the functional spec actually true, rather than
aspirational.

"Where applicable" distinguishes Registry-discovered skills from built-in
workflow gates:
- **Registry skills (`private-*`)**: Carry `registry_entry_id` (revision ID pinned from Agent Registry) and `approval_scope` (parsed from `SKILL.md` YAML frontmatter).
- **Built-in orchestrator gates (`orchestrator-hitl-gate`, `orchestrator-execution-gate`)**: Carry `skill_version` (pinned to the orchestrator build SHA / package version), while `registry_entry_id = None` and `approval_scope = None` because built-in gates are hard-wired workflow nodes rather than Agent Registry-discovered skills.

See [`audit-log-entry.schema.json`](../../schemas/audit-log-entry.schema.json).

## 7. User Profile

User demographic profile, career milestones, family dependents, retirement timeline,
and qualitative financial goal notes. Captured and edited in the Profile & Policy Hub (`/profile`),
persisted to Firestore at `user_profiles/{user_id}`.

Notable fields:
- `user_id` — unique user identifier scoping profile data
- `full_name`, `email`, `date_of_birth`, `age` — demographic foundation
- `marital_status`, `dependents_count`, `family_members[]` — household context for risk capacity
- `employment_status`, `occupation`, `annual_income_usd`, `monthly_housing_payment_usd` — cashflow stability
- `target_retirement_age` — time horizon calibration anchor
- `risk_tolerance_notes`, `financial_goals_notes` — qualitative goal memory

See [`user-profile.schema.json`](../../schemas/user-profile.schema.json).

## 8. Drift Report

Output of the Portfolio Analysis skill. Compares current portfolio allocations
against the target allocation bands defined in the active IPS.

Notable fields:
- `user_id`, `as_of`, `ips_id`, `ips_version` — policy reference traceability
- `drift_detected` — boolean flag indicating if any asset class breached target min/max bounds
- `allocations[]` — per asset class: `current_percent`, `target_percent`, `min_percent`, `max_percent`, `drift_percent`, and `status` (`OK` / `DRIFTED`)

See [`drift-report.schema.json`](../../schemas/drift-report.schema.json).

## 9. Spending Report

Output of the Spending Analysis skill. Synthesizes 30-day cashflow metrics,
category spending breakdowns, savings rate, emergency reserve runway, and
spending anomaly detections.

Notable fields:
- `user_id`, `analysis_period_start`, `analysis_period_end`
- `total_income_usd`, `total_outflow_usd`, `net_savings_usd`, `savings_rate_percent`
- `reserve_months` — emergency reserve runway computed against average monthly outflow
- `category_breakdown[]` — normalized spending per category with percentage of outflow
- `anomalies[]` — detected spending anomalies meeting dual-condition triggers ($> $100 and $> 2.0\times$ category monthly average)

See [`spending-report.schema.json`](../../schemas/spending-report.schema.json).

## 10. Account Transaction

Canonical transaction schema representing individual bank or credit account movements.
Ingested into BigQuery dataset `portfolio_copilot`, table `checking_transactions`.

Notable fields:
- `user_id` — row-level security identifier for CTE sandboxing
- `transaction_date` — `YYYY-MM-DD`
- `amount` — signed amount (positive for income/inflows, negative for expenses/outflows)
- `description`, `raw_category`, `normalized_category` — standardized taxonomy categories

See [`account-transaction.schema.json`](../../schemas/account-transaction.schema.json).

## 11. W-2 Document

Structured IRS Form W-2 Wage and Tax Statement parsed by Google Cloud Document AI
and persisted to Firestore collection `w2_documents`.

Notable fields:
- `id` — unique identifier for the parsed statement (`w2-{uuid}`)
- `user_id` — user scoping identifier
- `tax_year` — reporting tax year (e.g. 2024)
- `employer` — `name`, `ein`, and `address`
- `employee` — `name`, masked SSN (`***-**-XXXX`), and `address`
- `wages_and_compensation` — Box 1 wages, Box 2 federal tax withheld, Boxes 3-6 Social Security & Medicare taxes
- `box12_items[]` — elective deferrals and benefits (`code`, `description`, `amount_usd`, e.g. 401(k), HSA)
- `box13_checkboxes` — statutory employee, retirement plan, third party sick pay
- `state_taxes[]` / `local_taxes[]` — state and local wage and tax withholding allocations
- `confidence_score` — average Document AI entity confidence score (0.0 to 1.0)
- `status` — ingestion status (`SUCCESS`, `FAILED`, `PENDING_REVIEW`)

See [`w2-document.schema.json`](../../schemas/w2-document.schema.json).

## Changing these contracts

Additive changes (new optional field) are fine as a normal PR. A breaking
change (renamed/removed/retyped field) affects every skill at once —
open an ADR explaining why before making it, the same bar as any other
architectural decision.
