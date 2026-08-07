#!/bin/bash
set -e

# Usage: ./register_skill.sh [SKILL_NAME] [PROJECT_ID] [REGION]

SKILL_NAME=${1:-goals-onboarding}
PROJECT_ID=${2:-$PROJECT_ID}
REGION=${3:-${REGION:-global}}

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

# Extract display name and description from SKILL.md YAML frontmatter
DISPLAY_NAME=$(python3 -c "
import sys
with open(sys.argv[1], 'r') as f:
    lines = f.readlines()
in_yaml = False
for line in lines:
    if line.strip() == '---':
        if not in_yaml:
            in_yaml = True
            continue
        else:
            break
    if in_yaml and line.startswith('name:'):
        print(line.split('name:', 1)[1].strip())
        break
" "$SKILL_DIR/SKILL.md")

DESCRIPTION=$(python3 -c "
import sys
with open(sys.argv[1], 'r') as f:
    lines = f.readlines()
in_yaml = False
yaml_lines = []
for line in lines:
    if line.strip() == '---':
        if not in_yaml:
            in_yaml = True
            continue
        else:
            break
    if in_yaml:
        yaml_lines.append(line)
desc_lines = []
in_desc = False
for line in yaml_lines:
    if line.startswith('description:'):
        desc = line.split('description:', 1)[1].strip().lstrip('>-\"\'').rstrip('\"\'')
        if desc:
            desc_lines.append(desc)
        in_desc = True
    elif in_desc and line.startswith(' '):
        desc_lines.append(line.strip())
    else:
        in_desc = False
print(' '.join(desc_lines))
" "$SKILL_DIR/SKILL.md")

if [ -z "$DISPLAY_NAME" ]; then
  DISPLAY_NAME="$SKILL_NAME"
fi

# Package the skill directory into a ZIP file in /tmp/
ZIP_PATH="/tmp/${SKILL_NAME}.zip"
echo "Creating ZIP payload at $ZIP_PATH..."
rm -f "$ZIP_PATH"
(cd "$SKILL_DIR" && zip -r "$ZIP_PATH" .)

# Determine if the skill is registered as private-{skill} or {skill}
if gcloud alpha agent-registry skills describe "private-${SKILL_NAME}" --project="$PROJECT_ID" --location="$REGION" &>/dev/null; then
  REGISTERED_NAME="private-${SKILL_NAME}"
elif gcloud alpha agent-registry skills describe "${SKILL_NAME}" --project="$PROJECT_ID" --location="$REGION" &>/dev/null; then
  REGISTERED_NAME="${SKILL_NAME}"
else
  REGISTERED_NAME="${SKILL_NAME}"
fi

# Step 1: Create skill resource without payload, or update metadata if it already exists
echo "Calling Agent Registry API (Step 1: Resource Metadata)..."
if gcloud alpha agent-registry skills describe "$REGISTERED_NAME" --project="$PROJECT_ID" --location="$REGION" &>/dev/null; then
  echo "Skill '$REGISTERED_NAME' already exists in project $PROJECT_ID ($REGION). Updating display name and description..."
  gcloud alpha agent-registry skills update "$REGISTERED_NAME" \
    --project="$PROJECT_ID" \
    --location="$REGION" \
    --display-name="$DISPLAY_NAME" \
    --description="$DESCRIPTION" || echo "Note: Metadata update skipped or unchanged."
else
  echo "Creating new skill '$REGISTERED_NAME' (display-name: '$DISPLAY_NAME')..."
  gcloud alpha agent-registry skills create "$REGISTERED_NAME" \
    --project="$PROJECT_ID" \
    --location="$REGION" \
    --type=simple \
    --display-name="$DISPLAY_NAME" \
    --description="$DESCRIPTION"

  # Re-evaluate registered name in case the registry assigned a private- prefix
  if gcloud alpha agent-registry skills describe "private-${SKILL_NAME}" --project="$PROJECT_ID" --location="$REGION" &>/dev/null; then
    REGISTERED_NAME="private-${SKILL_NAME}"
  fi
fi

# Step 2: Create a skill revision with the payload
REV_ID="rev-$(date +%Y%m%d-%H%M%S)"
echo "Calling Agent Registry API (Step 2: Creating Revision '$REV_ID' with payload)..."
gcloud alpha agent-registry skills revisions create "$REV_ID" \
  --skill="$REGISTERED_NAME" \
  --project="$PROJECT_ID" \
  --location="$REGION" \
  --payload="$ZIP_PATH"

# Step 3: Ensure default revision is set to the newly created revision and activate skill
FULL_REV_NAME="projects/${PROJECT_ID}/locations/${REGION}/skills/${REGISTERED_NAME}/revisions/${REV_ID}"
echo "Calling Agent Registry API (Step 3: Setting default revision to '$FULL_REV_NAME' and activating)..."
gcloud alpha agent-registry skills update "$REGISTERED_NAME" \
  --project="$PROJECT_ID" \
  --location="$REGION" \
  --default-revision="$FULL_REV_NAME" \
  --target-state="TARGET_STATE_ACTIVE"

echo "Skill '$SKILL_NAME' successfully registered/updated as '$REGISTERED_NAME' with default revision '$REV_ID'."
