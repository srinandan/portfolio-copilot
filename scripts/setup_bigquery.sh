#!/bin/bash
set -e

# Usage: ./setup_bigquery.sh [PROJECT_ID]

PROJECT_ID=${1:-$PROJECT_ID}
if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project)
fi

DATASET_NAME="portfolio_copilot"
TABLE_NAME="chase_transactions"

echo "Setting up BigQuery in project $PROJECT_ID..."

# Create dataset if it doesn't exist
bq mk --project_id="$PROJECT_ID" --dataset --force=false "${DATASET_NAME}" || echo "Dataset ${DATASET_NAME} already exists."

# Create table
bq mk \
  --project_id="$PROJECT_ID" \
  --table \
  --force=false \
  "${DATASET_NAME}.${TABLE_NAME}" \
  user_id:STRING,transaction_date:DATE,amount:FLOAT64,description:STRING,raw_category:STRING,normalized_category:STRING || echo "Table ${TABLE_NAME} already exists."

echo "BigQuery setup complete."
