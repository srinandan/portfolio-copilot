#!/bin/bash
set -e

# Usage: ./register_skill.sh [SKILL_NAME] [PROJECT_ID] [REGION]

SKILL_NAME=${1:-goals-onboarding}
PROJECT_ID=${2:-$PROJECT_ID}
REGION=${3:-${REGION:-us-central1}}

if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "")
fi

if [ -z "$PROJECT_ID" ]; then
  echo "Error: PROJECT_ID is not set and could not be determined from gcloud config."
  exit 1
fi

SKILL_DIR="skills/$SKILL_NAME"
if [ ! -d "$SKILL_DIR" ]; then
  echo "Error: Skill directory $SKILL_DIR does not exist."
  exit 1
fi

if [ ! -f "$SKILL_DIR/SKILL.md" ]; then
  echo "Error: $SKILL_DIR/SKILL.md does not exist. SKILL.md is required."
  exit 1
fi

echo "Registering skill '$SKILL_NAME' in project $PROJECT_ID ($REGION)..."

# Package the skill directory into a ZIP file in /tmp/
ZIP_PATH="/tmp/${SKILL_NAME}.zip"
echo "Creating ZIP payload at $ZIP_PATH..."
rm -f "$ZIP_PATH"
(cd "$SKILL_DIR" && zip -r "$ZIP_PATH" .)

# The API expects private-{skill} for self-registered skills
REGISTERED_NAME="private-${SKILL_NAME}"

# Register the skill using gcloud alpha agent-registry skills create
echo "Calling Agent Registry API..."
gcloud alpha agent-registry skills create "$REGISTERED_NAME" \
  --project="$PROJECT_ID" \
  --location="$REGION" \
  --type=simple \
  --payload="$ZIP_PATH"

echo "Skill '$SKILL_NAME' successfully registered as '$REGISTERED_NAME'."
