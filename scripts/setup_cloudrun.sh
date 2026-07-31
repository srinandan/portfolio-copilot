#!/bin/bash
set -e

# Usage: ./setup_cloudrun.sh [PROJECT_ID] [REGION]

PROJECT_ID=${1:-$PROJECT_ID}
REGION=${2:-${REGION:-us-central1}}

if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project)
fi

echo "Setting up Cloud Run placeholders in project $PROJECT_ID ($REGION)..."

# Enable Cloud Run API
gcloud services enable run.googleapis.com --project="$PROJECT_ID"

# Placeholder image
IMAGE="us-docker.pkg.dev/cloudrun/container/hello"

SERVICES=("orchestrator" "gateway" "frontend")

for SERVICE in "${SERVICES[@]}"; do
  echo "Deploying placeholder for Cloud Run service: $SERVICE"
  gcloud run deploy "$SERVICE" \
    --project="$PROJECT_ID" \
    --image="$IMAGE" \
    --region="$REGION" \
    --allow-unauthenticated \
    --max-instances=1 \
    --quiet || echo "Failed to deploy $SERVICE"
done

echo "Cloud Run placeholders setup complete."
