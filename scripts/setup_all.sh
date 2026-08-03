#!/bin/bash
set -e

# Main script to run all infrastructure scaffolding scripts
# Usage: ./setup_all.sh [PROJECT_ID] [REGION]

PROJECT_ID=${1:-$PROJECT_ID}
REGION=${2:-${REGION:-us-central1}}

if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project)
fi
if [ -z "$PROJECT_ID" ]; then
  echo "Error: PROJECT_ID is not set and could not be determined from gcloud config."
  exit 1
fi

echo "========================================"
echo "Starting GCP Infra Scaffolding"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "========================================"

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "--- 1. Setting up Secret Manager ---"
bash "$DIR/setup_secrets.sh" "$PROJECT_ID"

echo "--- 2. Setting up BigQuery ---"
bash "$DIR/setup_bigquery.sh" "$PROJECT_ID"

echo "--- 3. Setting up Firestore ---"
bash "$DIR/setup_firestore.sh" "$PROJECT_ID" "$REGION"

echo "--- 4. Setting up Cloud Run ---"
bash "$DIR/setup_cloudrun.sh" "$PROJECT_ID" "$REGION"

echo "--- 5. Setting up Agent Engine ---"
bash "$DIR/setup_agent_engine.sh" "$PROJECT_ID" "$REGION"

echo "--- 6. Registering Agent Skills ---"
bash "$DIR/register_all_skills.sh" "$PROJECT_ID" "global"

echo "========================================"
echo "All GCP Infra scaffolding completed successfully!"
echo "========================================"
