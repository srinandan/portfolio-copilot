#!/bin/bash
set -e

# Usage: ./revoke_skill.sh [SKILL_NAME] [PROJECT_ID] [REGION]
#
# Revokes a skill by setting its targetState to TARGET_STATE_DISABLED.
# The next planner cycle will observe the skill as absent and (once #25
# lands) emit a SKILL_REVOKED audit entry.
#
# Example:
#   ./revoke_skill.sh research my-gcp-project global
#
# See docs/demos/live-revocation.md for the end-to-end demo.

SKILL_NAME=${1:?"Usage: revoke_skill.sh SKILL_NAME [PROJECT_ID] [REGION]"}
PROJECT_ID=${2:-$PROJECT_ID}
REGION=${3:-${REGION:-global}}

if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "")
fi

if [ -z "$PROJECT_ID" ]; then
  echo "Error: PROJECT_ID is not set and could not be determined from gcloud config."
  exit 1
fi

# Skills are registered as private-<name>
REGISTERED_NAME="private-${SKILL_NAME}"
FULL_PATH="projects/${PROJECT_ID}/locations/${REGION}/skills/${REGISTERED_NAME}"

echo "Revoking skill '$FULL_PATH'..."

# Try gcloud alpha agent-registry skills update first; if unavailable, fall back
# to curl against agentregistry.googleapis.com.
if gcloud alpha agent-registry skills update --help >/dev/null 2>&1; then
  gcloud alpha agent-registry skills update "$REGISTERED_NAME" \
    --project="$PROJECT_ID" \
    --location="$REGION" \
    --target-state=DISABLED \
    --quiet
else
  TOKEN=$(gcloud auth print-access-token)
  curl -s -X PATCH \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    "https://agentregistry.googleapis.com/v1/${FULL_PATH}?updateMask=targetState" \
    -d '{"targetState": "TARGET_STATE_DISABLED"}' >/dev/null
fi

echo "Skill '$SKILL_NAME' revoked. The next planner cycle will exclude it."
echo "To restore: ./scripts/restore_skill.sh $SKILL_NAME $PROJECT_ID $REGION"
