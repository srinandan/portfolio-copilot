# ADR-0026: Tax-loss harvesting — a new skill, a tax-lot data model, and wash-sale as a deterministic compliance rule

## Status

**Proposed.** Planned as the first "grow the catalog" skill after the
intent-driven planner shipped ([ADR-0022](0022-intent-driven-skill-planning.md)).
Tracked in issue #337. No code yet; this ADR records the decision and its
shape before the tax-lot data model — the load-bearing prerequisite — is built.

Refines [ADR-0016](0016-deterministic-primitives-in-orchestrator.md): the loss
identification, lot selection, and wash-sale math are deterministic in the
orchestrator; the LLM writes only the `rationale`. Consistent with
[ADR-0005](0005-managed-agents-hybrid-evaluation.md): the skill never holds an
Alpaca order-placement credential and its authority ends at a drafted action.
Builds on [ADR-0020](0020-typed-document-ingestion-and-onboarding-prefill.md)
for lot ingestion and [ADR-0022](0022-intent-driven-skill-planning.md) for
additive, manifest-driven routing.

## Context

Tax-loss harvesting (TLH) — realizing an unrealized loss in a taxable account
to offset gains, subject to the IRS wash-sale rule — is a natural next
capability for a personal-finance copilot. It is also a deliberate test of two
of the project's central claims:

1. **ADR-0022's "drop a skill and go."** If routing is truly additive, a new
   skill plus its manifest should be selectable with no `planner.py` edit. TLH
   is the first genuinely new skill since that pipeline landed (N=6 → N=7).
2. **The deterministic-compliance thesis.** The whole point of the demo is that
   safety is a property of the artifact graph and deterministic rules, not the
   model's judgement. The **wash-sale rule** is a near-perfect fit: a bright-line,
   date-driven constraint that a deterministic Reviewer rule can enforce
   independently of whatever the LLM proposed.

Two forces shape the design.

**The compliance spine already exists and should be reused, not rebuilt.** A
TLH skill that `produces: [proposed_action]` inherits the entire existing
governance path for free: the Reviewer carries `mandatory_if: proposed_action
exists`, and the HITL approval card and Alpaca execution gate are triggered
structurally by the same artifact. The skill itself is therefore small.

**The data model is the real gap.** TLH is impossible to do correctly on
today's holdings. `Position`
(`orchestrator/src/orchestrator/contracts/holdings.py`) carries `ticker`,
`quantity`, `asset_class`, `market_value_usd`, and `account_type` — but **no
cost basis and no acquisition date**. Unrealized loss needs cost basis; the
wash-sale ±30-day window needs acquisition dates. One hook already exists:
`account_type` (`taxable` / `retirement`), and TLH applies only to taxable
lots. The foundational work is a **tax-lot model**, not a skill.

## Decision

Ship TLH as a manifest-routed skill built on a new tax-lot data model, with the
wash-sale rule enforced as a deterministic Reviewer check.

### 1. A tax-lot / cost-basis data model (the foundation)

Introduce a `TaxLot` — per lot: `lot_id`, `ticker`, `acquired_at`,
`quantity`, `cost_basis_usd`, `account_type`. Defined as a canonical schema in
`/schemas`, with a matched Go (`pkg/contracts/`) and Pydantic
(`orchestrator/src/orchestrator/contracts/`) contract pair kept honest by the
existing `scripts/sync-schemas.sh` CI drift check.

Lots are **ingested, not skill-produced** (extending ADR-0020's typed holdings
snapshot). A holdings snapshot **without** lots must remain loadable — the
aggregate `Position` fields stay backward-compatible, and lot-dependent
features degrade gracefully (TLH declines to draft rather than erroring).

### 2. A deterministic TLH primitive

`orchestrator/src/orchestrator/primitives/tax_loss_harvesting.py`, mirroring
the shape of `calculate_draft_action`:

- filter to `account_type == taxable`;
- per lot, unrealized loss = `market_value − cost_basis` (losses only), ranked
  by harvestable magnitude;
- flag short-term vs long-term from `acquired_at`;
- reuse the existing IPS constraint checks (`excluded_tickers`,
  `excluded_sectors`, concentration);
- return the candidate harvest trade, or `None` when nothing is worth
  harvesting. **An empty result is correct** — never invent a trade.

The Managed Agent writes only the `rationale`; every number is authoritative
from the primitive (the ADR-0016 boundary).

### 3. The skill and its manifest

`skills/tax-loss-harvesting/` ships `SKILL.md`, an evalset, and a
`manifest.json`:

```json
{
  "id": "tax-loss-harvesting",
  "summary": "Identifies taxable positions held at an unrealized loss and drafts a wash-sale-safe harvest trade.",
  "applies_when": "The user asks to harvest losses, reduce taxes, offset gains, or realize a loss for tax purposes.",
  "requires": ["holdings", "active_ips", "tax_lots"],
  "produces": ["proposed_action"],
  "parallelizable": false
}
```

A `TAX_LOTS` artifact is added to the `Artifact` enum
(`orchestrator/src/orchestrator/skills/manifest.py`) and classified in
`PRELOADED_ARTIFACTS`, since it is ingested rather than produced by a skill.
Because the skill `produces: [proposed_action]`, the resolver injects the
Reviewer, HITL, and execution gates automatically — no new gate wiring.

### 4. Wash-sale as a deterministic Reviewer rule (the compliance centerpiece)

Add `rule_wash_sale` to `orchestrator/src/orchestrator/reviewer/rules.py`,
registered in `RULES` next to `rule_excluded_ticker`. It **fails** (routes to
the human) when a harvest SELL realizes a loss on a ticker for which any lot of
a substantially-identical security was acquired within ±30 days of the sell.
The rule is mirrored in `skills/reviewer/SKILL.md`'s "Rules to evaluate"
section and the reviewer evalset — the rules module's own header requires both
sides to move together, or the LLM's version silently wins.

The LLM proposes; a deterministic rule independently blocks a wash-sale
violation before the human ever sees it. This is the governance narrative the
project is built to show, applied to a real tax constraint — a candidate third
demo centerpiece alongside live-revocation and adversarial-resilience.

### 5. Routing and surface

A harvest-intent include rule is added to
`orchestrator/src/orchestrator/planning/intent.py` (verbs: `harvest`,
`tax loss`, `offset gains`, `realize a loss`), with an eval fixture asserting
`prompt → [tax-loss-harvesting]`. The harvest proposal flows through the
existing `ApprovalCard`; the frontend's Policy Safety Checklist gains a
wash-sale line.

## Consequences

- **The compliance spine is reused, not extended.** No new gate, no new
  approval path — TLH rides the `proposed_action` machinery. Adding the skill
  touches its own directory, the intent rule, and the `TAX_LOTS` artifact;
  `planner.py` is untouched, which is the ADR-0022 claim under test.
- **The tax-lot model is a real, cross-cutting data change** spanning schemas,
  both contract languages, ingestion, and testdata — most of the effort, and
  reusable by future tax-aware features (e.g. gain/loss-aware rebalancing,
  which `action-drafting` explicitly deferred).
- **Wash-sale is deliberately conservative in v1** (exact-ticker match only).
  The "substantially identical" ETF-equivalence case (`VOO`/`IVV`/`SPY`) is a
  named follow-up, not v1 scope — a false negative there is a missed block, so
  it is called out rather than half-built.
- **Backward compatibility is a hard requirement.** Lotless snapshots stay
  loadable; TLH degrades to "declines to draft" rather than erroring, so the
  data-model change never breaks existing flows.
- **A new tax domain enters the demo,** with its own correctness burden — the
  primitive and the wash-sale rule each carry hand-calculated tests, and the
  skill carries an evalset, per the project's standing rule that the
  deterministic rule and the reviewer SKILL.md/evalset never drift.

## Rollout

Phased, foundation-first (issue #337 carries the task-level breakdown):

- **Phase 1 — Tax-lot data model.** Schema, Go + Pydantic contracts, drift
  check, ingestion, testdata fixture. No TLH behaviour; backward-compatible.
- **Phase 2 — Deterministic primitive.** `find_harvest_candidates` with
  hand-calculated tests.
- **Phase 3 — The skill.** `SKILL.md`, `manifest.json`, evalset, `TAX_LOTS`
  artifact, registration.
- **Phase 4 — Wash-sale rule.** `rule_wash_sale` + its reviewer SKILL.md /
  evalset mirror + tests.
- **Phase 5 — Planning, UI, docs.** Intent rule + fixture, ApprovalCard
  checklist line, CHANGELOG.

Sequencing: TLH is larger than the two open ~1-day governance fixes (#173
Reviewer re-check after HITL edit, #169 per-session cost cap). Close **#173
first** — the edit-after-review gap is exactly the hole a wash-sale-sensitive
harvest would most want closed — then build TLH on solid ground.

## Open questions

1. **Lot storage** — extend `Position` with an optional `lots` list vs. a
   separate `TaxLotSnapshot` Firestore collection.
2. **"Substantially identical"** — v1 exact-ticker match only, or a
   configurable equivalence set (`VOO`/`IVV`/`SPY`)? Leaning exact-ticker for
   v1, with equivalence as a documented follow-up.
3. **Replacement buy** — sell-only (one clean `ProposedAction`) vs. also
   proposing a non-identical replacement to keep market exposure. Leaning
   sell-only for v1.
