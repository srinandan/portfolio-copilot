#!/bin/bash
set -e

# Usage: ./scripts/load_test_data.sh [PROJECT_ID] [LOCATION]
# Loads canonical test fixtures into GCP BigQuery and Firestore.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PROJECT_ID=${1:-${PROJECT_ID}}
LOCATION=${2:-${LOCATION:-${REGION:-us-central1}}}

if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project 2>/dev/null || true)
fi

if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "(unset)" ]; then
  echo "Error: PROJECT_ID is not set. Specify as first argument, set PROJECT_ID env var, or configure gcloud."
  exit 1
fi

echo "=================================================="
echo "Portfolio Copilot - Loading Test Fixtures to GCP"
echo "Project:  $PROJECT_ID"
echo "Location: $LOCATION"
echo "=================================================="

# Ensure BigQuery dataset & table exist
echo "1. Ensuring BigQuery schema exists..."
"$SCRIPT_DIR/setup_bigquery.sh" "$PROJECT_ID"

# Ensure Firestore database exists
echo "2. Ensuring Firestore database exists..."
"$SCRIPT_DIR/setup_firestore.sh" "$PROJECT_ID" "$LOCATION"

# Run Python loader to seed data
echo "3. Seeding data fixtures..."
if command -v uv &> /dev/null; then
  uv run --with jsonschema --with google-cloud-bigquery --with google-cloud-firestore python "$SCRIPT_DIR/load_test_data.py" --project="$PROJECT_ID" --location="$LOCATION"
elif command -v python3 &> /dev/null; then
  python3 "$SCRIPT_DIR/load_test_data.py" --project="$PROJECT_ID" --location="$LOCATION"
fi

echo "=================================================="
echo "✓ All test fixtures loaded successfully!"
echo "=================================================="
