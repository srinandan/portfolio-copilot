#!/bin/bash
set -e

# Usage: ./restore_skill.sh [SKILL_NAME] [PROJECT_ID] [REGION]
#
# Restores a skill by setting its targetState back to TARGET_STATE_ACTIVE.
#
# Example:
#   ./restore_skill.sh research my-gcp-project global

SKILL_NAME=${1:?"Usage: restore_skill.sh SKILL_NAME [PROJECT_ID] [REGION]"}
PROJECT_ID=${2:-$PROJECT_ID}
REGION=${3:-${REGION:-global}}

if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "")
fi

if [ -z "$PROJECT_ID" ]; then
  echo "Error: PROJECT_ID is not set and could not be determined from gcloud config."
  exit 1
fi

REGISTERED_NAME="private-${SKILL_NAME}"
FULL_PATH="projects/${PROJECT_ID}/locations/${REGION}/skills/${REGISTERED_NAME}"

echo "Restoring skill '$FULL_PATH'..."

if gcloud alpha agent-registry skills update --help >/dev/null 2>&1; then
  gcloud alpha agent-registry skills update "$REGISTERED_NAME" \
    --project="$PROJECT_ID" \
    --location="$REGION" \
    --target-state=ACTIVE \
    --quiet
else
  TOKEN=$(gcloud auth print-access-token)
  curl -s -X PATCH \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    "https://agentregistry.googleapis.com/v1/${FULL_PATH}?updateMask=targetState" \
    -d '{"targetState": "TARGET_STATE_ACTIVE"}' >/dev/null
fi

echo "Skill '$SKILL_NAME' restored to TARGET_STATE_ACTIVE."
