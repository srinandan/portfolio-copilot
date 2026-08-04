#!/bin/bash
set -e

# Usage: ./setup_secrets.sh [PROJECT_ID]

PROJECT_ID=${1:-$PROJECT_ID}

if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project)
fi

echo "Setting up Secret Manager secrets in project $PROJECT_ID..."

# Enable Secret Manager API
gcloud services enable secretmanager.googleapis.com --project="$PROJECT_ID"

# Alpaca credentials: two secrets, key + secret
for SECRET in ALPACA_API_KEY_ID ALPACA_API_SECRET; do
  if ! gcloud secrets describe "$SECRET" --project="$PROJECT_ID" &>/dev/null; then
    echo "Creating secret: $SECRET"
    gcloud secrets create "$SECRET" --replication-policy="automatic" \
      --labels="app=portfolio-copilot" --project="$PROJECT_ID"

    echo -n "dummy-replace-me-with-real-value" | \
      gcloud secrets versions add "$SECRET" --data-file=- --project="$PROJECT_ID"
    echo "Secret $SECRET created with dummy value."
  else
    echo "Secret $SECRET already exists. Ensuring labels..."
    gcloud secrets update "$SECRET" --update-labels="app=portfolio-copilot" \
      --project="$PROJECT_ID" --quiet 2>/dev/null || true
  fi
done

# Ensure MANAGED_AGENT_ID secret exists
MA_SECRET_NAME="MANAGED_AGENT_ID"
MA_DEFAULT_VALUE="projects/${PROJECT_ID}/locations/us-central1/agents/portfolio-copilot-worker"
if ! gcloud secrets describe "$MA_SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
  echo "Creating secret: $MA_SECRET_NAME"
  gcloud secrets create "$MA_SECRET_NAME" --replication-policy="automatic" --labels="app=portfolio-copilot" --project="$PROJECT_ID"
  echo -n "$MA_DEFAULT_VALUE" | gcloud secrets versions add "$MA_SECRET_NAME" --data-file=- --project="$PROJECT_ID"
  echo "Secret $MA_SECRET_NAME created with default value."
fi

# Grant Secret Manager access to the Agent Platform Service Agent
# (Required during deployment when secrets are passed as env vars to Reasoning Engine)
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

echo "Secret Manager setup complete."
