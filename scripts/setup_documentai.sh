#!/bin/bash
set -e

# Usage: ./setup_documentai.sh [PROJECT_ID] [LOCATION]

PROJECT_ID=${1:-$PROJECT_ID}
LOCATION=${2:-${DOCUMENT_AI_LOCATION:-us}}

if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
fi

if [ -z "$PROJECT_ID" ]; then
  echo "Error: PROJECT_ID is required."
  exit 1
fi

echo "Setting up Google Cloud Document AI in project $PROJECT_ID (location: $LOCATION)..."

# 1. Enable Document AI API
echo "Enabling Document AI API (documentai.googleapis.com)..."
gcloud services enable documentai.googleapis.com --project="$PROJECT_ID"

# 2. Grant Document AI permissions to frontend service account
FRONTEND_SA="portfolio-copilot-frontend-sa@${PROJECT_ID}.iam.gserviceaccount.com"
echo "Configuring Document AI IAM permissions for $FRONTEND_SA..."

for ROLE in roles/documentai.apiUser roles/documentai.viewer; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$FRONTEND_SA" \
    --role="$ROLE" \
    --condition=None \
    --quiet || echo "Warning: could not bind $ROLE to $FRONTEND_SA (service account might not exist yet; run setup_cloudrun.sh first)"
done

# 3. Create or retrieve Form W-2 Processor
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo "Ensuring Form W-2 Processor exists in $PROJECT_ID ($LOCATION)..."
PROCESSOR_ID=$(cd "$DIR/.." && go run ./scripts/setup_processor.go -project="$PROJECT_ID" -location="$LOCATION" | tail -n1)

echo "========================================"
echo "Document AI setup complete."
echo "Processor ID: $PROCESSOR_ID"
echo "Location:     $LOCATION"
echo "========================================"
