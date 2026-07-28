# ADR-0002: Split data layer — BigQuery + Firestore

## Status
Accepted

## Context
Needed somewhere to persist Chase transaction data, portfolio holdings,
the IPS document, and the approval/audit log. Vertex AI Memory Bank was
already decided for soft/semantic memory, but isn't built for bulk
structured data or transactional writes.

## Options considered

**Firestore alone.** Sufficient for this project's scale (thousands of
transaction rows, not millions) and does support native aggregation
queries. Rejected as the *sole* store because it can't do the kind of ad
hoc grouping/trend analysis ("why did dining spend jump in June?") that
makes for a compelling NL-to-SQL demo moment — a real showcase-worthy
capability that Firestore's model doesn't support.

**BigQuery alone.** Rejected. BigQuery is an analytical warehouse:
query latency is typically seconds, and row-level DML is rate-limited and
eventually consistent. The operational path — checking current holdings
mid-conversation, writing an approval decision, updating holdings after a
trade — needs millisecond point reads, real transactional writes, and
row-level concurrency control. Running every "check my holdings" through a
warehouse query is both slower and needlessly expensive (billed per bytes
scanned).

## Decision
Split by access pattern, not by convenience:

- **BigQuery** — Chase transaction data only, so Spending Analysis can do
  genuine NL-to-SQL analytics
- **Firestore** — IPS document, portfolio holdings, approval/audit log:
  everything the agents read/write on every turn

## Consequences
- Two systems to operate instead of one, but each is used for what it's
  actually good at
- The analytics demo moment (NL-to-SQL against real data) is preserved
- If the analytics showcase were ever dropped, collapsing to Firestore
  alone would be a reasonable simplification
