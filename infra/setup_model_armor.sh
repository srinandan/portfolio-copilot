#!/bin/bash
set -e

# Usage: ./setup_model_armor.sh [PROJECT_ID] [ENABLE_MODEL_ARMOR] [ENFORCEMENT_MODE]
#
# Arguments:
#   PROJECT_ID          GCP Project ID (default: current gcloud configured project or $PROJECT_ID)
#   ENABLE_MODEL_ARMOR  Whether floor settings enforcement is enabled: "true" | "false" (default: true)
#   ENFORCEMENT_MODE    Sanitization mode: "INSPECT_ONLY" | "INSPECT_AND_BLOCK" (default: INSPECT_ONLY)

PROJECT_ID=${1:-${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || echo "")}}
ENABLE_MODEL_ARMOR=${2:-${ENABLE_MODEL_ARMOR:-true}}
ENFORCEMENT_MODE=${3:-${ENFORCEMENT_MODE:-INSPECT_ONLY}}

if [ -z "$PROJECT_ID" ]; then
  echo "Error: PROJECT_ID is not set and could not be determined from gcloud config." >&2
  exit 1
fi

echo "========================================"
echo "Configuring Google Cloud Model Armor"
echo "Project: $PROJECT_ID"
echo "Enforcement: $ENABLE_MODEL_ARMOR (default: true)"
echo "Mode: $ENFORCEMENT_MODE"
echo "========================================"

echo "--- 1. Enabling Model Armor API ---"
gcloud services enable modelarmor.googleapis.com --project="$PROJECT_ID" --quiet

echo "--- 2. Applying Floor Settings ---"
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$DIR/.." && pwd )"

ENABLE_FLAG="--enable"
if [ "$ENABLE_MODEL_ARMOR" = "false" ] || [ "$ENABLE_MODEL_ARMOR" = "0" ] || [ "$ENABLE_MODEL_ARMOR" = "disabled" ]; then
  ENABLE_FLAG="--disable"
fi

if command -v uv &> /dev/null; then
  uv run --project "$REPO_ROOT/orchestrator" python "$DIR/model_armor_floor_settings.py" \
    --project="$PROJECT_ID" \
    $ENABLE_FLAG \
    --mode="$ENFORCEMENT_MODE"
elif command -v python3 &> /dev/null; then
  python3 "$DIR/model_armor_floor_settings.py" \
    --project="$PROJECT_ID" \
    $ENABLE_FLAG \
    --mode="$ENFORCEMENT_MODE"
else
  echo "Warning: Python environment not found. Attempting gcloud CLI update..."
  gcloud model-armor floorsettings update \
    --full-uri="projects/${PROJECT_ID}/locations/global/floorSetting" \
    --enable-floor-setting-enforcement="$([ "$ENABLE_FLAG" = "--enable" ] && echo "TRUE" || echo "FALSE")" \
    --add-integrated-services=AI_PLATFORM,GOOGLE_MCP_SERVER \
    --enable-google-mcp-server-cloud-logging \
    --google-mcp-server-enforcement-type="$ENFORCEMENT_MODE" \
    --enable-vertex-ai-cloud-logging \
    --vertex-ai-enforcement-type="$ENFORCEMENT_MODE" \
    --enable-multi-language-detection \
    --malicious-uri-filter-settings-enforcement=ENABLED \
    --basic-config-filter-enforcement=ENABLED \
    --pi-and-jailbreak-filter-settings-enforcement=ENABLE \
    --pi-and-jailbreak-filter-settings-confidence-level=medium-and-above \
    --quiet
fi

echo "========================================"
echo "Model Armor Floor Settings configured successfully!"
echo "========================================"
