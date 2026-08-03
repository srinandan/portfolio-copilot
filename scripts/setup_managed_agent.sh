#!/bin/bash
set -e

# Usage: ./setup_managed_agent.sh [PROJECT_ID] [REGION]

PROJECT_ID=${1:-$PROJECT_ID}
REGION=${2:-${REGION:-us-central1}}

if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project)
fi

echo "Setting up worker Managed Agent in project $PROJECT_ID ($REGION)..."

# Enable required Google Cloud APIs
gcloud services enable secretmanager.googleapis.com aiplatform.googleapis.com --project="$PROJECT_ID"

# Grant Secret Manager access to Agent Platform Service Agent
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)" 2>/dev/null || echo "")
if [ -n "$PROJECT_NUMBER" ]; then
  AI_SERVICE_AGENT="service-${PROJECT_NUMBER}@gcp-sa-aiplatform.iam.gserviceaccount.com"
  echo "Granting Secret Manager access to Agent Platform Service Agent ($AI_SERVICE_AGENT)..."
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${AI_SERVICE_AGENT}" \
    --role="roles/secretmanager.secretAccessor" \
    --condition=None \
    --quiet || echo "Warning: Failed to grant Secret Manager access to AI Service Agent $AI_SERVICE_AGENT"
fi

# Run deployment script to register worker MA and store MANAGED_AGENT_ID secret
if command -v uv &> /dev/null; then
    echo "Running Python worker MA deployment script with uv..."
    uv run --with "google-cloud-secret-manager>=2.16.0" --with "google-auth" --with "click" python scripts/deploy_managed_agent.py --project="$PROJECT_ID" --location="$REGION"
elif command -v python3 &> /dev/null; then
    echo "Running Python worker MA deployment script..."
    python3 scripts/deploy_managed_agent.py --project="$PROJECT_ID" --location="$REGION"
else
    echo "No python or uv found. Storing fallback secret via gcloud..."
    MANAGED_AGENT_ID="projects/${PROJECT_ID}/locations/${REGION}/agents/portfolio-copilot-worker"
    if ! gcloud secrets describe "MANAGED_AGENT_ID" --project="$PROJECT_ID" &>/dev/null; then
      gcloud secrets create "MANAGED_AGENT_ID" --replication-policy="automatic" --labels="app=portfolio-copilot" --project="$PROJECT_ID"
    fi
    echo -n "$MANAGED_AGENT_ID" | gcloud secrets versions add "MANAGED_AGENT_ID" --data-file=- --project="$PROJECT_ID"
fi

echo "Worker Managed Agent setup complete."
