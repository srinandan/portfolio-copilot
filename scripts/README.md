# Automation and Infrastructure Scripts (`scripts/`)

This directory contains the operational, provisioning, deployment, data loading, and testing scripts for **Portfolio Copilot**.

---

## Script Catalog

### 1. Environment & Infrastructure Setup

| Script | Description | Usage |
|---|---|---|
| [`setup_all.sh`](setup_all.sh) | Runs end-to-end setup across GCP (secrets, BigQuery, Firestore, Cloud Run, Managed Agent, Agent Runtime, and skill registration) in sequence. | `./scripts/setup_all.sh <PROJECT_ID> <REGION>` |
| [`setup_secrets.sh`](setup_secrets.sh) | Creates Secret Manager secrets (`ALPACA_API_KEY_ID`, `ALPACA_API_SECRET`, `MANAGED_AGENT_ID`) and binds access permissions. | `./scripts/setup_secrets.sh <PROJECT_ID> <REGION>` |
| [`setup_bigquery.sh`](setup_bigquery.sh) | Creates BigQuery dataset `portfolio_copilot` and `chase_transactions` / `checking_transactions` tables. | `./scripts/setup_bigquery.sh <PROJECT_ID> <REGION>` |
| [`setup_firestore.sh`](setup_firestore.sh) | Provisions the default Firestore database in Native mode. | `./scripts/setup_firestore.sh <PROJECT_ID> <REGION>` |
| [`setup_cloudrun.sh`](setup_cloudrun.sh) | Deploys the frontend service to Cloud Run with dedicated service account (`portfolio-copilot-frontend-sa`). | `./scripts/setup_cloudrun.sh <PROJECT_ID> <REGION>` |
| [`setup_managed_agent.sh`](setup_managed_agent.sh) | Provisions the worker Managed Agent (`portfolio-copilot-worker`) and stores its ID in Secret Manager. | `./scripts/setup_managed_agent.sh <PROJECT_ID> <REGION>` |
| [`setup_agent_engine.sh`](setup_agent_engine.sh) | Sets up Agent Runtime IAM roles and Agent Identity permissions. | `./scripts/setup_agent_engine.sh <PROJECT_ID> <REGION>` |
| [`setup_cloudbuild_triggers.sh`](setup_cloudbuild_triggers.sh) | Configures Developer Connect GitHub connection and tag-triggered Cloud Build pipelines for automatic releases. | `./scripts/setup_cloudbuild_triggers.sh <PROJECT_ID> <REGION>` |

---

### 2. Deployment and Runtime Administration

| Script | Description | Usage |
|---|---|---|
| [`deploy_agent_engine.py`](deploy_agent_engine.py) | Deploys the Python orchestrator container to Vertex AI Agent Runtime via `vertexai.Client().agent_engines`. | `python3 scripts/deploy_agent_engine.py --project=<PROJECT_ID> --location=<REGION> --container-uri=<IMAGE_URI>` |
| [`deploy_managed_agent.py`](deploy_managed_agent.py) | Deploys or updates the worker Managed Agent (`portfolio-copilot-worker`) in Vertex AI. | `python3 scripts/deploy_managed_agent.py --project=<PROJECT_ID> --location=<REGION>` |
| [`agent_engine_admin.py`](agent_engine_admin.py) | CLI tool to list, describe, query, fetch logs, or delete deployed Agent Engines. | `python3 scripts/agent_engine_admin.py list --project=<PROJECT_ID> --location=<REGION>` |

---

### 3. Agent Registry & Skill Management

| Script | Description | Usage |
|---|---|---|
| [`register_all_skills.sh`](register_all_skills.sh) | Registers all 6 runtime skills from `skills/` to the Agent Registry as `private-<skill-name>`. | `./scripts/register_all_skills.sh <PROJECT_ID> <LOCATION>` |
| [`register_skill.sh`](register_skill.sh) | Packages and registers or updates a specific skill with the Agent Registry. | `./scripts/register_skill.sh <skill-name> <PROJECT_ID> <LOCATION>` |
| [`revoke_skill.sh`](revoke_skill.sh) | Sets a skill's lifecycle state to `DEPRECATED` in the Agent Registry for live revocation testing. | `./scripts/revoke_skill.sh <skill-name>` |
| [`restore_skill.sh`](restore_skill.sh) | Restores a skill's lifecycle state to `ACTIVE` in the Agent Registry. | `./scripts/restore_skill.sh <skill-name>` |

---

### 4. Data Loading and Schema Synchronization

| Script | Description | Usage |
|---|---|---|
| [`load_test_data.sh`](load_test_data.sh) | Validates fixtures and populates BigQuery transactions and Firestore collections (`ips`, `holdings`, `liabilities`, `user_profiles`, `drift_reports`, `spending_reports`). | `./scripts/load_test_data.sh <PROJECT_ID> <REGION>` |
| [`load_test_data.py`](load_test_data.py) | Python script validating test fixtures against `/schemas` and loading them into GCP. Supports `--dry-run`. | `python3 scripts/load_test_data.py --dry-run` |
| [`sync-schemas.sh`](sync-schemas.sh) | Verifies that Go struct tags and Pydantic schemas match JSON Schema definitions in `/schemas`. | `./scripts/sync-schemas.sh` |

---

### 5. Demos, Evals, and Smoke Tests

| Script | Description | Usage |
|---|---|---|
| [`demo_live_revocation.py`](demo_live_revocation.py) | Interactive demo script showing live skill revocation mid-session and dynamic graph replanning. | `cd orchestrator && uv run python ../scripts/demo_live_revocation.py` |
| [`test_managed_agent_skills.py`](test_managed_agent_skills.py) | Executes worker Managed Agent against registered skills to verify tool execution and responses. | `python3 scripts/test_managed_agent_skills.py` |
| [`build_evalsets.py`](build_evalsets.py) | Compiles `.evalset.json` test datasets for ADK skill evaluations across all candidate skills. | `python3 scripts/build_evalsets.py` |
