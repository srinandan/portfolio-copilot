#!/bin/bash
set -e

# Usage: ./setup_bigquery.sh [PROJECT_ID]

PROJECT_ID=${1:-$PROJECT_ID}
if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project)
fi

DATASET_NAME="portfolio_copilot"
TABLE_NAMES=("checking_transactions")

echo "Setting up BigQuery in project $PROJECT_ID..."

# Create dataset if it doesn't exist
if ! bq show --project_id="$PROJECT_ID" "${DATASET_NAME}" &>/dev/null; then
  echo "Creating BigQuery dataset: ${DATASET_NAME}"
  bq mk --project_id="$PROJECT_ID" --dataset --label=app:portfolio-copilot "${DATASET_NAME}"
else
  echo "Dataset ${DATASET_NAME} already exists. Ensuring labels..."
  bq update --project_id="$PROJECT_ID" --set_label=app:portfolio-copilot "${DATASET_NAME}" 2>/dev/null || true
fi

# Create tables
for TABLE_NAME in "${TABLE_NAMES[@]}"; do
  if ! bq show --project_id="$PROJECT_ID" "${DATASET_NAME}.${TABLE_NAME}" &>/dev/null; then
    echo "Creating BigQuery table: ${DATASET_NAME}.${TABLE_NAME}"
    bq mk \
      --project_id="$PROJECT_ID" \
      --table \
      --label=app:portfolio-copilot \
      "${DATASET_NAME}.${TABLE_NAME}" \
      user_id:STRING,transaction_date:DATE,amount:FLOAT64,description:STRING,raw_category:STRING,normalized_category:STRING
  else
    echo "Table ${TABLE_NAME} already exists. Ensuring labels..."
    bq update --project_id="$PROJECT_ID" --set_label=app:portfolio-copilot "${DATASET_NAME}.${TABLE_NAME}" 2>/dev/null || true
  fi
done

echo "BigQuery setup complete."
