#!/bin/bash
set -e

# Usage: ./setup_cloudrun.sh [PROJECT_ID] [REGION]

PROJECT_ID=${1:-$PROJECT_ID}
REGION=${2:-${REGION:-us-central1}}

if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project)
fi

echo "Setting up Cloud Run service (portfolio-copilot-frontend) in project $PROJECT_ID ($REGION)..."

# Enable Cloud Run API
gcloud services enable run.googleapis.com --project="$PROJECT_ID"

# 1. Create dedicated service account for unified frontend service
# Note: orchestrator deploys to Agent Runtime, not Cloud Run (ADR-0008).

FRONTEND_SA="portfolio-copilot-frontend-sa@${PROJECT_ID}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "$FRONTEND_SA" --project="$PROJECT_ID" &>/dev/null; then
  echo "Creating service account: portfolio-copilot-frontend-sa"
  gcloud iam service-accounts create portfolio-copilot-frontend-sa \
    --project="$PROJECT_ID" \
    --display-name="Portfolio Copilot frontend"
else
  echo "Service account portfolio-copilot-frontend-sa already exists."
fi

# 2. Grant least-privilege IAM roles to frontend-sa
# - Firestore (roles/datastore.user): reads holdings, writes audit log directly (ADR-0003)
# - BigQuery (roles/bigquery.dataViewer): fan-out chart reads
# Note: Frontend does NOT need Secret Manager access (Alpaca access is orchestrator-only per ADR-0005).
echo "Configuring IAM policy bindings for portfolio-copilot-frontend-sa..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$FRONTEND_SA" \
  --role="roles/datastore.user" \
  --condition=None \
  --quiet

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$FRONTEND_SA" \
  --role="roles/bigquery.dataViewer" \
  --condition=None \
  --quiet

# 3. Deploy Cloud Run placeholder with explicit service account
IMAGE="us-docker.pkg.dev/cloudrun/container/hello"

echo "Deploying Cloud Run service: portfolio-copilot-frontend"
gcloud run deploy portfolio-copilot-frontend \
  --project="$PROJECT_ID" \
  --image="$IMAGE" \
  --region="$REGION" \
  --service-account="$FRONTEND_SA" \
  --labels="app=portfolio-copilot,component=frontend" \
  --no-allow-unauthenticated \
  --max-instances=1 \
  --quiet || echo "Failed to deploy portfolio-copilot-frontend"

echo "Cloud Run setup complete."
