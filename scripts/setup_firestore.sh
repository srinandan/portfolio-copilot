#!/bin/bash
set -e

# Usage: ./setup_firestore.sh [PROJECT_ID] [REGION]

PROJECT_ID=${1:-$PROJECT_ID}
REGION=${2:-${REGION:-us-central1}}

if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project)
fi

echo "Setting up Firestore in project $PROJECT_ID ($REGION)..."

# Enable Firestore API
gcloud services enable firestore.googleapis.com --project="$PROJECT_ID"

# Create default database if it doesn't exist
gcloud firestore databases create --project="$PROJECT_ID" --location="$REGION" --type=firestore-native || echo "Firestore default database already exists."

echo "Firestore setup complete."
