# ADR-0015: Real user data through Antigravity sandbox (personal-use scope)

## Status
**Accepted.** Supersedes the data-isolation clause of [ADR-0005](0005-managed-agents-hybrid-evaluation.md) for personal-use demo scope.

## Context
ADR-0005 originally restricted data passed into the Pre-GA Managed Agents sandbox to synthetic or public market research data to mitigate data leakage risks. 

In the Portfolio Copilot personal-use demo, the assistant operates on the project owner's personal financial data (own Chase transaction records, paper-trading portfolio holdings, and Investment Policy Statement). Restricting skills to synthetic data limits the utility of onboarding interviews, spending analytics, and drift evaluations.

## Decision
Personal financial data (own Chase transactions, own paper-trade holdings, own IPS) may be routed through Antigravity's sandbox as tool inputs and Managed Agent invocation inputs, subject to strict boundary constraints:
1. **Personal-Use Demo Only:** Applies solely to the project owner's personal data. Multi-tenant or third-party user data is explicitly out of scope and would require re-evaluating sandbox data privacy terms upon GA.
2. **Credential Isolation:** Payloads passed to the Interactions API must never contain broker credentials (e.g. Alpaca API secrets), banking credentials, or write tokens.
3. **Audit Trail Verifiability:** Every data flow and Managed Agent invocation is recorded in the Firestore audit log with full actor, skill version, and timestamp metadata.

## Consequences
- Enables rich, end-to-end reasoning over real personal transactions and portfolio positions.
- Non-goals (multi-tenant / multi-user support) become load-bearing safety constraints.
- Dispatch validation layers assert that no credential strings or secret environment variables are passed to the Interactions API.
