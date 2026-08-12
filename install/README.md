# Install

## Prerequisites

- `gcloud` CLI, authenticated, with a GCP project you can administer
- `python3` (3.11+), `pip`, `uv` (recommended for Python packaging)
- `go` (for the Go backend server)
- `node`/`npm` (for the Vue frontend)

## First-time setup

Provisions Secret Manager, BigQuery, Firestore, Cloud Run, Managed Agent workers, and Agent Runtime, in the order each depends on the last:

```bash
./scripts/setup_all.sh <PROJECT_ID> <REGION>
```

This runs, in sequence:

1. `setup_secrets.sh`, creates `ALPACA_API_KEY_ID`, `ALPACA_API_SECRET`, and `MANAGED_AGENT_ID` secrets (placeholder values, replace Alpaca keys with real paper-trading credentials afterward), granting the Agent Platform Service Agent access to fetch them during deployment.
2. `setup_bigquery.sh`, creates the `portfolio_copilot.chase_transactions` dataset and table.
3. `setup_firestore.sh`, provisions the Firestore database.
4. `setup_cloudrun.sh`, deploys `frontend` (unified web host and backend API server) to Cloud Run with its own dedicated, least-privilege service account, not the default compute service account.
5. `setup_managed_agent.sh`, provisions and deploys the worker Managed Agent (`scripts/deploy_managed_agent.py`) and stores its resource ID in Secret Manager as `MANAGED_AGENT_ID`.
6. `setup_agent_engine.sh`, provisions Agent Runtime for the orchestrator (`scripts/deploy_agent_engine.py`), including least-privilege Agent Identity IAM roles.
7. `register_all_skills.sh`, registers all 6 runtime skills (`goals-onboarding`, `spending-analysis`, `portfolio-analysis`, `research`, `action-drafting`, `reviewer`) in the Agent Registry.

Each script also runs standalone if you only need to redo one step:
`./scripts/setup_bigquery.sh <PROJECT_ID>`, etc.

### Replace the placeholder Alpaca keys

```bash
echo -n "<your real Alpaca paper-trading key ID>" | \
  gcloud secrets versions add ALPACA_API_KEY_ID --data-file=- --project=<PROJECT_ID>

echo -n "<your real Alpaca paper-trading secret>" | \
  gcloud secrets versions add ALPACA_API_SECRET --data-file=- --project=<PROJECT_ID>
```

### Credentials & Secret Flow

Credentials (`MANAGED_AGENT_ID`, `ALPACA_API_KEY_ID`, and `ALPACA_API_SECRET`) are stored in Google Cloud Secret Manager and resolved automatically at runtime:

1. **Secret Manager**: Stored securely in Secret Manager (`projects/<PROJECT_ID>/secrets/<SECRET_NAME>/versions/latest`) and provisioned via `scripts/setup_secrets.sh`.
2. **Startup Resolution (`secret_loader.py`)**: When the orchestrator boots in Agent Runtime or locally, `secret_loader.py` checks environment variables first. If not set, it fetches the secrets from Secret Manager using the default service account credentials (`roles/secretmanager.secretAccessor`) and binds them to environment variables (`os.environ`).
3. **Startup Validation**: At orchestrator boot (`planner.py`), `verify_required_secrets()` validates that all required secrets can be resolved. In production/strict mode, if any are missing, startup fails immediately with a clear `SecretLoadError` rather than crashing mid-order during execution.
4. **Executor Access**: Executors (`alpaca.py`, `worker.py`) read the resolved credentials from environment variables.

## Registering a skill

Each skill under `skills/` needs registering with the real Agent Registry before the orchestrator can discover it:

```bash
# Register a single skill:
./scripts/register_skill.sh <skill-name> <PROJECT_ID> <REGION>
# e.g. ./scripts/register_skill.sh goals-onboarding <PROJECT_ID> us-central1

# Or register all runtime skills at once:
./scripts/register_all_skills.sh <PROJECT_ID> <REGION>
```

Zips the skill directory and registers it as `private-<skill-name>`. Re-run this any time a skill's `SKILL.md` or supporting files change, this pushes a new revision, it doesn't mutate the existing one.

## Loading test and seed data

To bring your own data instead of the fixtures, see
[`testdata/README.md`](../testdata/README.md) for the input formats — the
transactions CSV schema and the holdings / liabilities / IPS JSON documents.

To seed your BigQuery dataset and Firestore database with canonical test fixtures from `testdata/`:

```bash
# Setup schemas and seed BigQuery + Firestore:
./scripts/load_test_data.sh <PROJECT_ID> <REGION>

# Or run dry-run validation locally without GCP calls:
python3 scripts/load_test_data.py --dry-run
```

This populates:
- **BigQuery (`portfolio_copilot.chase_transactions`)**: 4 months of transaction history exercising the dual-condition spending anomaly rule.
- **Firestore (`ips/ips_demo_001_v1`, `holdings/demo_user`, `liabilities/demo_user`)**: Canonical active IPS reference policy, multi-asset class holdings (with out-of-band equity drift and unclassified crypto asset class), and credit liabilities.

## Verify installation

To verify that the worker Managed Agent is provisioned and reachable in your GCP project without needing a full UI test:

```bash
export PROJECT_ID=<your-project-id>
export RUN_INTEGRATION_TESTS=1
cd orchestrator && uv run pytest tests/integration/test_managed_agent_provisioned.py -v
```

This smoke test verifies that `resolve_managed_agent_id()` loads a live `MANAGED_AGENT_ID` from Secret Manager or environment variables and can instantiate an ADK `ManagedAgent` worker.

## Running locally

```bash
# orchestrator (Python)
cd orchestrator && uv pip install -e ".[dev]" && uv run pytest

# frontend UI & Go backend server
cd frontend && npm install && npm run build
go build -o bin/server ./frontend/server && ./bin/server
```

## Updating / redeploying after code changes

Depends on what changed:

- **Frontend code**: use the Makefile — `make deploy-frontend` (or `make -C frontend deploy`). For a tagged release, push a `v*` tag and the Cloud Build triggers set up by `scripts/setup_cloudbuild_triggers.sh` build and deploy both services automatically (see below).
- **Worker Managed Agent code**: re-run
  `./scripts/setup_managed_agent.sh <PROJECT_ID> <REGION>` (or `python scripts/deploy_managed_agent.py --project=<PROJECT_ID> --location=<REGION>`).
- **Orchestrator code**: use the Makefile — `make deploy-orchestrator` (or `make -C orchestrator deploy`) to build and redeploy to Agent Runtime.
- **Full stack (both services)**: use `make deploy` from repository root.
- **A skill's `SKILL.md` or contents**: re-run `register_skill.sh` for
  that skill (or `register_all_skills.sh`), per above.
- **Infra changes** (new secrets, new BigQuery columns, IAM changes):
  re-run the specific `setup_*.sh` script that owns that resource, not
  `setup_all.sh` wholesale, unless you're provisioning a fresh project.

## Cloud Build: tag-triggered releases via Developer Connect

To wire the repo up so pushing a git tag builds and deploys both
services (orchestrator and frontend), run:

```bash
./scripts/setup_cloudbuild_triggers.sh <PROJECT_ID> <REGION>
```

This uses [Developer Connect (2nd-gen Cloud Build GitHub integration)](https://docs.cloud.google.com/build/docs/automating-builds/github/connect-repo-github?generation=2nd-gen#gcloud)
to:

1. Enable the required APIs (`developerconnect`, `cloudbuild`, `artifactregistry`, `run`, `secretmanager`).
2. Create a Developer Connect GitHub connection. The first run pauses and prints
   an installation URL — open it, install the Cloud Build GitHub App on
   `srinandan/portfolio-copilot`, then re-run the script.
3. Link the GitHub repo to the connection.
4. Create an Artifact Registry Docker repo (`portfolio-copilot`) in the target region.
5. Grant the Cloud Build service account `roles/run.admin`,
   `roles/iam.serviceAccountUser`, and `roles/artifactregistry.writer`.
6. Create one tag-triggered build trigger per service (orchestrator and frontend), all firing on tags
   matching `^v.*$` (e.g. `v0.1.0`, `v1.2.3-rc1`).

To cut a release once the triggers are in place:

```bash
git tag v0.1.0
git push origin v0.1.0
```

Both builds start in parallel; each pushes a versioned image to
Artifact Registry (`<region>-docker.pkg.dev/<project>/portfolio-copilot/<service>:v0.1.0`)
and deploys it — the frontend to Cloud Run, the orchestrator to
Agent Platform Agent Runtime via
[`ReasoningEngineSpec.container_spec`](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/deploy)
per [ADR-0008](../docs/adr/0008-python-for-orchestrator.md).

### Triggering builds manually

Use the root `Makefile` or per-service Makefiles (`orchestrator/Makefile`,
`frontend/Makefile`):

- `make deploy-orchestrator` (or `make -C orchestrator deploy`) — builds the container and deploys orchestrator to Agent Runtime.
- `make deploy-frontend` (or `make -C frontend deploy`) — builds the container and deploys frontend/server to Cloud Run.
- `make deploy` — deploys both services in sequence.
- `make local` (in `frontend/` or `orchestrator/`) — runs the service on your machine (uv/go/npm as appropriate).

Environment overrides (`GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`,
`_COMMIT_SHA`) work the same way across all Makefiles.

## Demos

### Live Skill Revocation

Demonstrates revoking a runtime skill mid-session via the Agent Registry and observing the next planning cycle adapt without errors or restarts:

```bash
export PROJECT_ID=<your-project-id>
export GOOGLE_CLOUD_LOCATION=global
export SKILL_TO_REVOKE=research   # or any registered skill
cd orchestrator && uv run python ../scripts/demo_live_revocation.py

# Restore the revoked skill afterward:
./scripts/restore_skill.sh $SKILL_TO_REVOKE
```

See [Live Skill Revocation](../docs/demos/live-revocation.md) for step-by-step documentation and expected audit trail output.
