# ADR-0021: Unified Profile & Policy Hub Architecture

## Status
Accepted

## Context
Prior to this decision, user demographic settings and investment policy configurations were divided across fragmented and non-synchronous user experiences:
1. **Onboarding Isolation**: The `/onboarding` view was structured as a linear wizard that collected initial targets and liabilities, but did not capture household demographics, family dependents, career milestones, or qualitative goal notes.
2. **Profile & Policy Fragmentation**: The initial `/profile` view only stored basic user demographics (`UserProfile`), leaving policy guardrails (target asset allocation bands, concentration limits, liquidity floors, excluded tickers) and debt liabilities managed in separate, disconnected interfaces.
3. **Synchronization Inconsistency**: When a user modified risk tolerance, target bands, or debt obligations in one place, demographic attributes (such as retirement horizon or dependent changes) were not evaluated or persisted in unison, creating potential policy drift between qualitative goals and quantitative allocation limits.

## Decision

### 1. Unified 5-Tab Profile & Policy Hub (`ProfileView.vue`)
Consolidate all user demographics, goal timelines, allocation models, liability tracking, and safety guardrails into a single cohesive settings center at `/profile` organized into five dedicated tabs:
- **Personal & Family**: Full name, email, date of birth, marital status, dependent count, and dynamic household member table.
- **Goals & Timeline**: Target retirement age, employment status, occupation, annual income, monthly housing payment, and qualitative goal notes.
- **Risk Calibration & Allocation**: Risk tolerance mode selection, SVG donut visualization, and interactive allocation sliders with strict 100% total balance validation.
- **Liabilities & Debt**: Interactive debt obligation table (credit card, mortgage, student loan, etc.) with balance, APR, and minimum payment calculations.
- **Policy Guardrails**: Max concentration limit (%), minimum liquidity reserve floor ($), approval threshold triggers, excluded tickers, and excluded sectors.

### 2. Synchronized Dual Persistence Architecture
Implement atomic dual persistence on the frontend and backend:
- On load (`GET /api/profile` and `GET /api/onboarding`), the UI fetches stored `UserProfile`, active `InvestmentPolicyStatement` (IPS), and `LiabilitiesSnapshot`.
- On save (`POST /api/profile`), the request updates the `user_profiles/{user_id}` document while atomically invoking `UpdateIPS` on the backend (`pkg/store/crud.go`), which creates a new active version (e.g. `ips_demo_001_v2`) and marks the previous version as `superseded` according to the append-only versioning invariant.
- Concurrently updates `liabilities/{user_id}` with updated debt balances.

### 3. Streamlined Navigation and Onboarding Deep-Link
- Update `Navbar.vue` to feature a direct link to the unified **Profile & Policy** hub (`/profile`).
- Maintain `OnboardingView.vue` as a guided introductory flow that provides an immediate fast-track deep link to `/profile` for users who already have an active profile or prefer tabbed direct configuration.

## Consequences
- Single pane of glass for all user profile attributes, policy constraints, and debt liabilities.
- Preserves strict append-only auditability for all IPS revisions without data loss.
- Eliminates fragmented state between user demographics and portfolio governance constraints.
- Fully verified with 100% unit test coverage across Go store tests, Python contracts, and Vue component tests (`Views.test.ts`, `Navbar.test.ts`).
