#!/bin/bash
set -e

DATASET_NAME="portfolio_copilot"
TABLE_NAME="chase_transactions"

# Create dataset if it doesn't exist
bq mk --dataset --force=false "${DATASET_NAME}" || echo "Dataset ${DATASET_NAME} already exists."

# Create table
bq mk \
  --table \
  --force=false \
  "${DATASET_NAME}.${TABLE_NAME}" \
  user_id:STRING,transaction_date:DATE,amount:FLOAT64,description:STRING,raw_category:STRING,normalized_category:STRING || echo "Table ${TABLE_NAME} already exists."

echo "BigQuery setup complete."
