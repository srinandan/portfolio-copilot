# Install

## Prerequisites

- `gcloud` CLI, authenticated, with a GCP project you can administer
- `python3`, `pip`
- `go` (for the gateway)
- `node`/`npm` (for the frontend, once it exists)

## First-time setup

Provisions Secret Manager, BigQuery, Firestore, Cloud Run, and Agent
Runtime, in the order each depends on the last:

```bash
./scripts/setup_all.sh <PROJECT_ID> <REGION>
```

This runs, in sequence:

1. `setup_secrets.sh`, creates the `ALPACA_API_KEY` secret (placeholder
   value, replace it with a real Alpaca paper-trading key afterward),
   grants the Agent Platform Service Agent access to fetch it during
   deployment
2. `setup_bigquery.sh`, creates the `portfolio_copilot.chase_transactions`
   dataset and table
3. `setup_firestore.sh`, provisions the Firestore database
4. `setup_cloudrun.sh`, deploys `gateway` and `frontend` (once it
   exists) to Cloud Run, each with its own dedicated, least-privilege
   service account, not the default compute service account
5. `setup_agent_engine.sh`, provisions Agent Runtime for the
   orchestrator, including Agent Identity configuration

Each script also runs standalone if you only need to redo one step:
`./scripts/setup_bigquery.sh <PROJECT_ID>`, etc.

### Replace the placeholder Alpaca key

```bash
echo -n "<your real Alpaca paper-trading API key>" | \
  gcloud secrets versions add ALPACA_API_KEY --data-file=- --project=<PROJECT_ID>
```

## Registering a skill

Each skill under `skills/` needs registering with the real Agent
Registry before the orchestrator can discover it:

```bash
./scripts/register_skill.sh <skill-name> <PROJECT_ID> <REGION>
# e.g. ./scripts/register_skill.sh goals-onboarding <PROJECT_ID> us-central1
```

Zips the skill directory and registers it as `private-<skill-name>`.
Re-run this any time a skill's `SKILL.md` or supporting files change,
this pushes a new revision, it doesn't mutate the existing one.

## Running locally

```bash
# orchestrator (Python)
cd orchestrator && pip install -e ".[dev]" && pytest

# gateway (Go)
cd gateway && go build ./... && go test ./...

# frontend (once it exists)
cd frontend && npm install && npm run dev
```

## Updating / redeploying after code changes

Depends on what changed:

- **Gateway or frontend code**: re-run
  `./scripts/setup_cloudrun.sh <PROJECT_ID> <REGION>`, or
  `gcloud run deploy` directly against the specific service if you only
  changed one
- **Orchestrator code**: re-run `python scripts/deploy_agent_engine.py`
  to redeploy to Agent Runtime
- **A skill's `SKILL.md` or contents**: re-run `register_skill.sh` for
  that skill, per above
- **Infra changes** (new secrets, new BigQuery columns, IAM changes):
  re-run the specific `setup_*.sh` script that owns that resource, not
  `setup_all.sh` wholesale, unless you're provisioning a fresh project

## Demos

- [Live Skill Revocation](../docs/demos/live-revocation.md) — Demonstrates
  revoking a skill mid-session and observing the next planning cycle adapt
  without errors or restarts.
