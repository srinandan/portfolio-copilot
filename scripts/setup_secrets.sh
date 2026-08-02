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

SECRET_NAME="ALPACA_API_KEY"
DUMMY_VALUE="dummy-alpaca-api-key-replace-me"

# Check if secret exists
if ! gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
  echo "Creating secret: $SECRET_NAME"
  gcloud secrets create "$SECRET_NAME" --replication-policy="automatic" --project="$PROJECT_ID"

  echo -n "$DUMMY_VALUE" | gcloud secrets versions add "$SECRET_NAME" --data-file=- --project="$PROJECT_ID"
  echo "Secret $SECRET_NAME created with dummy value."
else
  echo "Secret $SECRET_NAME already exists."
fi

echo "Secret Manager setup complete."
