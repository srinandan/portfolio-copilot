#!/bin/bash
set -e

# Usage: ./setup_agent_engine.sh [PROJECT_ID] [REGION]

PROJECT_ID=${1:-$PROJECT_ID}
REGION=${2:-${REGION:-us-central1}}

if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project)
fi

echo "Setting up Agent Engine in project $PROJECT_ID ($REGION)..."

# Enable Agent Platform / AI Platform API
gcloud services enable aiplatform.googleapis.com --project="$PROJECT_ID"

# 1. Grant Secret Manager access to Agent Platform Service Agent
# Per Agent Runtime docs: secrets used as environment variables are fetched during deployment
# by the Agent Platform Service Agent (service-PROJECT_NUMBER@gcp-sa-aiplatform.iam.gserviceaccount.com).
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)" 2>/dev/null || echo "")
if [ -n "$PROJECT_NUMBER" ]; then
  AI_SERVICE_AGENT="service-${PROJECT_NUMBER}@gcp-sa-aiplatform.iam.gserviceaccount.com"
  AI_RE_SERVICE_AGENT="service-${PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
  echo "Granting Secret Manager access to Agent Platform Service Agent ($AI_SERVICE_AGENT)..."
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${AI_SERVICE_AGENT}" \
    --role="roles/secretmanager.secretAccessor" \
    --condition=None \
    --quiet || echo "Warning: Failed to grant Secret Manager access to AI Service Agent $AI_SERVICE_AGENT"

  echo "Granting Artifact Registry reader access to Reasoning Engine Service Agents..."
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${AI_SERVICE_AGENT}" \
    --role="roles/artifactregistry.reader" \
    --condition=None \
    --quiet || echo "Warning: Failed to grant Artifact Registry reader to $AI_SERVICE_AGENT"
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${AI_RE_SERVICE_AGENT}" \
    --role="roles/artifactregistry.reader" \
    --condition=None \
    --quiet || echo "Warning: Failed to grant Artifact Registry reader to $AI_RE_SERVICE_AGENT"
fi

# 2. Grant project-level least-privilege IAM roles to Agent Runtime Agent Identities
if [ -n "$PROJECT_NUMBER" ]; then
  ORG_ID=$(gcloud projects describe "$PROJECT_ID" --format="value(parent.id)" 2>/dev/null || echo "")
  PARENT_TYPE=$(gcloud projects describe "$PROJECT_ID" --format="value(parent.type)" 2>/dev/null || echo "")

  if [ "$PARENT_TYPE" = "organization" ] && [ -n "$ORG_ID" ]; then
    PRINCIPAL_SET="principalSet://agents.global.org-${ORG_ID}.system.id.goog/attribute.platformContainer/aiplatform/projects/${PROJECT_NUMBER}"
  else
    PRINCIPAL_SET="principalSet://agents.global.project-${PROJECT_NUMBER}.system.id.goog/attribute.platformContainer/aiplatform/projects/${PROJECT_NUMBER}"
  fi

  echo "Configuring IAM policy bindings for Agent Identities ($PRINCIPAL_SET)..."
  # Firestore: IPS, holdings, liabilities
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="$PRINCIPAL_SET" \
    --role="roles/datastore.user" \
    --condition=None \
    --quiet || echo "Note: Datastore IAM binding on principalSet skipped or already configured"

  # BigQuery: spending analysis and job execution
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="$PRINCIPAL_SET" \
    --role="roles/bigquery.dataViewer" \
    --condition=None \
    --quiet || echo "Note: BigQuery dataViewer IAM binding on principalSet skipped or already configured"
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="$PRINCIPAL_SET" \
    --role="roles/bigquery.user" \
    --condition=None \
    --quiet || echo "Note: BigQuery user IAM binding on principalSet skipped or already configured"

  # Secret Manager: Alpaca API key & MANAGED_AGENT_ID
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="$PRINCIPAL_SET" \
    --role="roles/secretmanager.secretAccessor" \
    --condition=None \
    --quiet || echo "Note: Secret Manager IAM binding on principalSet skipped or already configured"

  # Agent Registry & Vertex AI: list authorized skills and invoke Managed Agents
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="$PRINCIPAL_SET" \
    --role="roles/agentregistry.viewer" \
    --condition=None \
    --quiet || echo "Note: Agent Registry IAM binding on principalSet skipped or already configured"
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="$PRINCIPAL_SET" \
    --role="roles/aiplatform.user" \
    --condition=None \
    --quiet || echo "Note: AI Platform User IAM binding on principalSet skipped or already configured"

  # Service Usage, Logging, and Monitoring
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="$PRINCIPAL_SET" \
    --role="roles/serviceusage.serviceUsageConsumer" \
    --condition=None \
    --quiet || echo "Note: Service Usage IAM binding on principalSet skipped or already configured"
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="$PRINCIPAL_SET" \
    --role="roles/logging.logWriter" \
    --condition=None \
    --quiet || echo "Note: Logging IAM binding on principalSet skipped or already configured"
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="$PRINCIPAL_SET" \
    --role="roles/monitoring.metricWriter" \
    --condition=None \
    --quiet || echo "Note: Monitoring IAM binding on principalSet skipped or already configured"
fi

# 3. Deploy Agent Engine instance with Agent Identity
if command -v uv &> /dev/null; then
    echo "Running Python deployment script with uv..."
    uv run --with "google-cloud-aiplatform[agent_engines]>=1.60.0" --with "cloudpickle" --with "google-auth" --with "click" python scripts/deploy_agent_engine.py --project="$PROJECT_ID" --location="$REGION"
elif command -v python3 &> /dev/null; then
    echo "Running Python deployment script (make sure vertexai, google-auth, click are installed)..."
    python3 scripts/deploy_agent_engine.py --project="$PROJECT_ID" --location="$REGION"
else
    echo "No python or uv found. Skipping Agent Engine deployment."
fi

echo "Agent Engine setup complete."
