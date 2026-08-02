#!/bin/bash
set -e

# Usage: ./setup_cloudrun.sh [PROJECT_ID] [REGION]

PROJECT_ID=${1:-$PROJECT_ID}
REGION=${2:-${REGION:-us-central1}}

if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project)
fi

echo "Setting up Cloud Run services in project $PROJECT_ID ($REGION)..."

# Enable Cloud Run API
gcloud services enable run.googleapis.com --project="$PROJECT_ID"

# 1. Create dedicated service accounts for Cloud Run services
# Note: orchestrator deploys to Agent Runtime, not Cloud Run (ADR-0008).

# Gateway Service Account
GATEWAY_SA="gateway-sa@${PROJECT_ID}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "$GATEWAY_SA" --project="$PROJECT_ID" &>/dev/null; then
  echo "Creating service account: gateway-sa"
  gcloud iam service-accounts create gateway-sa \
    --project="$PROJECT_ID" \
    --display-name="Portfolio Copilot gateway"
else
  echo "Service account gateway-sa already exists."
fi

# Frontend Service Account
FRONTEND_SA="frontend-sa@${PROJECT_ID}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "$FRONTEND_SA" --project="$PROJECT_ID" &>/dev/null; then
  echo "Creating service account: frontend-sa"
  gcloud iam service-accounts create frontend-sa \
    --project="$PROJECT_ID" \
    --display-name="Portfolio Copilot frontend"
else
  echo "Service account frontend-sa already exists."
fi

# 2. Grant least-privilege IAM roles to gateway-sa
# - Firestore (roles/datastore.user): reads holdings, writes audit log directly (ADR-0003)
# - BigQuery (roles/bigquery.dataViewer): fan-out chart reads
# Note: Gateway does NOT need Secret Manager access (Alpaca access is orchestrator-only per ADR-0005).
echo "Configuring IAM policy bindings for gateway-sa..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$GATEWAY_SA" \
  --role="roles/datastore.user" \
  --condition=None \
  --quiet

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$GATEWAY_SA" \
  --role="roles/bigquery.dataViewer" \
  --condition=None \
  --quiet

# Note: Frontend needs no GCP API roles at all (it calls gateway, never GCP services directly per ADR-0003).

# 3. Deploy Cloud Run placeholders with explicit service accounts
IMAGE="us-docker.pkg.dev/cloudrun/container/hello"

echo "Deploying Cloud Run service: gateway"
gcloud run deploy gateway \
  --project="$PROJECT_ID" \
  --image="$IMAGE" \
  --region="$REGION" \
  --service-account="$GATEWAY_SA" \
  --allow-unauthenticated \
  --max-instances=1 \
  --quiet || echo "Failed to deploy gateway"

echo "Deploying Cloud Run service: frontend"
gcloud run deploy frontend \
  --project="$PROJECT_ID" \
  --image="$IMAGE" \
  --region="$REGION" \
  --service-account="$FRONTEND_SA" \
  --allow-unauthenticated \
  --max-instances=1 \
  --quiet || echo "Failed to deploy frontend"

echo "Cloud Run setup complete."
