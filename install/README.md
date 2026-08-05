# Install

## Prerequisites

- `gcloud` CLI, authenticated, with a GCP project you can administer
- `python3` (3.11+), `pip`, `uv` (recommended for Python packaging)
- `go` (for the gateway)
- `node`/`npm` (for the frontend)

## First-time setup

Provisions Secret Manager, BigQuery, Firestore, Cloud Run, Managed Agent workers, and Agent Runtime, in the order each depends on the last:

```bash
./scripts/setup_all.sh <PROJECT_ID> <REGION>
```

This runs, in sequence:

1. `setup_secrets.sh`, creates `ALPACA_API_KEY_ID`, `ALPACA_API_SECRET`, and `MANAGED_AGENT_ID` secrets (placeholder values, replace Alpaca keys with real paper-trading credentials afterward), granting the Agent Platform Service Agent access to fetch them during deployment.
2. `setup_bigquery.sh`, creates the `portfolio_copilot.chase_transactions` dataset and table.
3. `setup_firestore.sh`, provisions the Firestore database.
4. `setup_cloudrun.sh`, deploys `gateway` and `frontend` to Cloud Run, each with its own dedicated, least-privilege service account, not the default compute service account.
5. `setup_managed_agent.sh`, provisions and deploys the worker Managed Agent (`scripts/deploy_managed_agent.py`) and stores its resource ID in Secret Manager as `MANAGED_AGENT_ID`.
6. `setup_agent_engine.sh`, provisions Agent Runtime for the orchestrator (`scripts/deploy_agent_engine.py`), including least-privilege Agent Identity IAM roles.
7. `register_all_skills.sh`, registers all 5 runtime skills (`goals-onboarding`, `spending-analysis`, `portfolio-analysis`, `research`, `action-drafting`) in the Agent Registry.

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

# Or register all 5 runtime skills at once:
./scripts/register_all_skills.sh <PROJECT_ID> <REGION>
```

Zips the skill directory and registers it as `private-<skill-name>`. Re-run this any time a skill's `SKILL.md` or supporting files change, this pushes a new revision, it doesn't mutate the existing one.

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

# gateway (Go)
cd gateway && go build ./... && go test ./...

# frontend (Vue + TypeScript)
cd frontend && npm install && npm run dev
```

## Updating / redeploying after code changes

Depends on what changed:

- **Gateway or frontend code**: use the per-service Makefile — `make -C gateway deploy` or `make -C frontend deploy` — which calls `gcloud builds submit --config=<service>/cloudbuild.yaml`. For a tagged release, push a `v*` tag and the Cloud Build triggers set up by `scripts/setup_cloudbuild_triggers.sh` build and deploy all three services automatically (see below).
- **Worker Managed Agent code**: re-run
  `./scripts/setup_managed_agent.sh <PROJECT_ID> <REGION>` (or `python scripts/deploy_managed_agent.py --project=<PROJECT_ID> --location=<REGION>`).
- **Orchestrator code**: re-run `python scripts/deploy_agent_engine.py`
  to redeploy to Agent Runtime.
- **A skill's `SKILL.md` or contents**: re-run `register_skill.sh` for
  that skill (or `register_all_skills.sh`), per above.
- **Infra changes** (new secrets, new BigQuery columns, IAM changes):
  re-run the specific `setup_*.sh` script that owns that resource, not
  `setup_all.sh` wholesale, unless you're provisioning a fresh project.

## Cloud Build: tag-triggered releases via Developer Connect

To wire the repo up so pushing a git tag builds and deploys all three
services (orchestrator, gateway, frontend), run:

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
6. Create one tag-triggered build trigger per service, all firing on tags
   matching `^v.*$` (e.g. `v0.1.0`, `v1.2.3-rc1`).

To cut a release once the triggers are in place:

```bash
git tag v0.1.0
git push origin v0.1.0
```

All three builds start in parallel; each pushes a versioned image to
Artifact Registry (`<region>-docker.pkg.dev/<project>/portfolio-copilot/<service>:v0.1.0`)
and deploys it to Cloud Run.

### Triggering builds manually

Use the per-service `Makefile` (`orchestrator/Makefile`, `gateway/Makefile`,
`frontend/Makefile`); each exposes two targets:

- `make local` — runs the service on your machine (uv/go/npm as appropriate).
- `make deploy` — calls `gcloud builds submit --config=<service>/cloudbuild.yaml`
  with `_COMMIT_SHA=$(git rev-parse --short HEAD)` and the current gcloud
  region as substitutions, then deploys to Cloud Run. No tag push required.

Environment overrides (`GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`,
`_COMMIT_SHA`) work the same way in both flows.

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
