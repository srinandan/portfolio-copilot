#!/bin/bash
set -e

# Main script to register all 5 Portfolio Copilot runtime skills in Agent Registry
# Usage: ./register_all_skills.sh [PROJECT_ID] [REGION]

PROJECT_ID=${1:-$PROJECT_ID}
REGION=${2:-${REGION:-global}}

if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "")
fi

if [ -z "$PROJECT_ID" ]; then
  echo "Error: PROJECT_ID is not set and could not be determined from gcloud config."
  exit 1
fi

echo "========================================"
echo "Registering Portfolio Copilot Skills"
echo "Project: $PROJECT_ID"
echo "Region:  $REGION"
echo "========================================"

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

SKILLS=(
  "goals-onboarding"
  "spending-analysis"
  "portfolio-analysis"
  "research"
  "action-drafting"
  "reviewer"
  "equity-research"
  "suitability"
)

for SKILL in "${SKILLS[@]}"; do
  echo "----------------------------------------"
  bash "$DIR/register_skill.sh" "$SKILL" "$PROJECT_ID" "$REGION"
done

echo "========================================"
echo "All runtime skills registered successfully in $PROJECT_ID ($REGION)!"
echo "========================================"
