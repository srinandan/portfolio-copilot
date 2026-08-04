# Demo: Live Skill Revocation

One of the two demo centerpieces from the [functional spec](../spec/00-overview.md).

Shows: revoking a skill's authorization mid-session causes the very next
planning cycle to exclude it, with no error, no restart, and a
`SKILL_REVOKED` audit entry that traces exactly what was revoked and when.

Reference: [ADR-0006 (targetState mechanism)](../adr/0006-agent-registry-api-alignment.md).

## Prerequisites

- All 5 skills registered in your project's Agent Registry (see
  [`scripts/register_all_skills.sh`](../../scripts/register_all_skills.sh))
- Managed Agent provisioned (see [`scripts/setup_managed_agent.sh`](../../scripts/setup_managed_agent.sh))
- `PROJECT_ID` and `GOOGLE_CLOUD_LOCATION` set

## Run it

```bash
export PROJECT_ID=my-gcp-project
export GOOGLE_CLOUD_LOCATION=global
export SKILL_TO_REVOKE=research     # or any registered skill

uv run --project orchestrator python scripts/demo_live_revocation.py
```

Expected output ends with:

```
✅ Live revocation demo PASSED — skill filtered on next cycle, audit entry present.
```

## What the demo does

1. Runs one planning cycle end-to-end, logs which skills were authorized.
2. PATCHes the chosen skill's `targetState` to `TARGET_STATE_DISABLED`.
3. Runs a second planning cycle in the same session.
4. Verifies:
   - The revoked skill is absent from cycle 2's authorized list.
   - A `SKILL_REVOKED` audit entry landed in Firestore, carrying the
     skill's prior `registry_entry_id` for full traceability.
5. Restores the skill's `targetState` to `TARGET_STATE_ACTIVE` so the demo
   is re-runnable.

## Troubleshooting

- **"Skill was not authorized on cycle 1"** — the skill isn't registered in
  the project. Register with `./scripts/register_skill.sh <name>`.
- **No `SKILL_REVOKED` audit entry** — check Firestore permissions for the
  orchestrator's Agent Identity; audit writes require `datastore.user`.
- **Skill still appears on cycle 2** — the revoke PATCH may have failed
  silently. Re-run with `./scripts/revoke_skill.sh <name>` manually and
  check `gcloud alpha agent-registry skills describe private-<name>`.

## Also see

- Sibling demo: [adversarial resilience](adversarial-resilience.md) — the
  Reviewer/Critic catches a poisoned tool result before HITL.
- ADR-0014 (Managed Agents as sub-agent execution layer).
- Issue #25 (this demo's tracking issue).
