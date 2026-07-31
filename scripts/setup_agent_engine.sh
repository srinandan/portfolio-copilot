#!/bin/bash
set -e

# Usage: ./setup_agent_engine.sh [PROJECT_ID] [REGION]

PROJECT_ID=${1:-$PROJECT_ID}
REGION=${2:-${REGION:-us-central1}}

if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project)
fi

echo "Setting up Agent Engine in project $PROJECT_ID ($REGION)..."

# Enable Vertex AI API
gcloud services enable aiplatform.googleapis.com --project="$PROJECT_ID"

# We use the python script to deploy the reasoning engine
# We check if uv is available (since this repo seems to use uv for python, based on AGENTS.md)
if command -v uv &> /dev/null; then
    # Create a temporary virtualenv to run the deployment script
    echo "Running Python deployment script with uv..."
    # Dependencies: vertexai, google-auth, click
    uv run --with "google-cloud-aiplatform>=1.60.0" --with "google-auth" --with "click" python scripts/deploy_agent_engine.py --project="$PROJECT_ID" --location="$REGION"
elif command -v python3 &> /dev/null; then
    echo "Running Python deployment script (make sure vertexai, google-auth, click are installed)..."
    python3 scripts/deploy_agent_engine.py --project="$PROJECT_ID" --location="$REGION"
else
    echo "No python or uv found. Skipping Agent Engine deployment."
fi

echo "Agent Engine setup complete."
