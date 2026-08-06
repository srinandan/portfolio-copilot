#!/bin/bash
set -e

# Provision Developer Connect + Cloud Build tag-triggered build triggers
# for the orchestrator and frontend services.
#
# Usage:
#   ./setup_cloudbuild_triggers.sh [PROJECT_ID] [REGION]
#
# What this does (in order):
#   1. Enables the Developer Connect, Cloud Build, Artifact Registry, and
#      Secret Manager APIs.
#   2. Creates a Developer Connect GitHub connection (OAuth-based, 2nd-gen
#      Cloud Build integration per
#      https://docs.cloud.google.com/build/docs/automating-builds/github/connect-repo-github?generation=2nd-gen).
#      The first run pauses and prints an installation URL — open it, install
#      the Cloud Build GitHub App on the srinandan/portfolio-copilot repo,
#      then re-run this script. Subsequent runs are idempotent.
#   3. Links the srinandan/portfolio-copilot repo to the connection.
#   4. Creates an Artifact Registry Docker repository for images.
#   5. Grants the Cloud Build service account permission to deploy to
#      Cloud Run and act as each service account.
#   6. Creates a tag-triggered build trigger per service that fires on any
#      pushed git tag matching ^v.* (e.g. v1.2.3, v0.1.0-rc1).
#
# Manual builds outside a tag push are still available via the per-service
# Makefiles (`make -C orchestrator deploy`, etc.), which call
# `gcloud builds submit --config=<service>/cloudbuild.yaml`.

PROJECT_ID=${1:-$PROJECT_ID}
REGION=${2:-${REGION:-us-central1}}

if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project)
fi
if [ -z "$PROJECT_ID" ]; then
  echo "Error: PROJECT_ID is not set and could not be determined from gcloud config."
  exit 1
fi

GITHUB_OWNER=${GITHUB_OWNER:-srinandan}
GITHUB_REPO=${GITHUB_REPO:-portfolio-copilot}
CONNECTION_NAME=${CONNECTION_NAME:-portfolio-copilot-github}
REPO_LINK_NAME=${REPO_LINK_NAME:-portfolio-copilot}
AR_REPO=${AR_REPO:-portfolio-copilot}
TAG_PATTERN=${TAG_PATTERN:-'^v.*$'}

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
CB_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

echo "========================================"
echo "Cloud Build tag triggers setup"
echo "  Project: $PROJECT_ID ($PROJECT_NUMBER)"
echo "  Region:  $REGION"
echo "  Repo:    ${GITHUB_OWNER}/${GITHUB_REPO}"
echo "  Trigger: tag pattern '${TAG_PATTERN}'"
echo "========================================"

echo "--- 1. Enable required APIs ---"
gcloud services enable \
  cloudbuild.googleapis.com \
  developerconnect.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  run.googleapis.com \
  --project="$PROJECT_ID"

echo "--- 2. Create Developer Connect GitHub connection ---"
if gcloud builds connections describe "$CONNECTION_NAME" \
     --project="$PROJECT_ID" --region="$REGION" &>/dev/null; then
  echo "Connection $CONNECTION_NAME already exists."
else
  echo "Creating Developer Connect connection $CONNECTION_NAME..."
  gcloud builds connections create github "$CONNECTION_NAME" \
    --project="$PROJECT_ID" \
    --region="$REGION"
fi

# Verify the GitHub App is installed. If installation_state.stage != COMPLETE,
# print the actionURI and stop — the user needs to click through the OAuth flow.
STAGE=$(gcloud builds connections describe "$CONNECTION_NAME" \
  --project="$PROJECT_ID" --region="$REGION" \
  --format='value(installationState.stage)' 2>/dev/null || echo "")

if [ "$STAGE" != "COMPLETE" ]; then
  ACTION_URI=$(gcloud builds connections describe "$CONNECTION_NAME" \
    --project="$PROJECT_ID" --region="$REGION" \
    --format='value(installationState.actionUri)' 2>/dev/null || echo "")
  echo ""
  echo "!!! GitHub App installation required !!!"
  echo "Open the following URL in a browser, authorize the Cloud Build"
  echo "GitHub App on the ${GITHUB_OWNER}/${GITHUB_REPO} repository, then"
  echo "re-run this script:"
  echo ""
  echo "  $ACTION_URI"
  echo ""
  exit 1
fi

echo "--- 3. Link the GitHub repository to the connection ---"
if gcloud builds repositories describe "$REPO_LINK_NAME" \
     --connection="$CONNECTION_NAME" \
     --project="$PROJECT_ID" --region="$REGION" &>/dev/null; then
  echo "Repository link $REPO_LINK_NAME already exists."
else
  gcloud builds repositories create "$REPO_LINK_NAME" \
    --remote-uri="https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}.git" \
    --connection="$CONNECTION_NAME" \
    --project="$PROJECT_ID" \
    --region="$REGION"
fi

REPO_RESOURCE="projects/${PROJECT_NUMBER}/locations/${REGION}/connections/${CONNECTION_NAME}/repositories/${REPO_LINK_NAME}"

echo "--- 4. Create Artifact Registry Docker repository ---"
if gcloud artifacts repositories describe "$AR_REPO" \
     --project="$PROJECT_ID" --location="$REGION" &>/dev/null; then
  echo "Artifact Registry repo $AR_REPO already exists."
else
  gcloud artifacts repositories create "$AR_REPO" \
    --repository-format=docker \
    --location="$REGION" \
    --description="Portfolio Copilot container images" \
    --project="$PROJECT_ID"
fi

echo "--- 5. Grant Cloud Build SA the roles it needs ---"
# roles/run.admin so frontend can `gcloud run deploy`; roles/aiplatform.user
# so orchestrator can create/update its Vertex AI Agent Engine (Agent Runtime);
# roles/iam.serviceAccountUser so the pipeline can act as per-service SAs on deploy;
# roles/artifactregistry.writer so it can push images.
for ROLE in roles/run.admin roles/aiplatform.user roles/iam.serviceAccountUser roles/artifactregistry.writer; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${CB_SA}" \
    --role="$ROLE" \
    --condition=None \
    --quiet
done

echo "--- 6. Create tag-triggered build triggers ---"
declare -A SERVICES=(
  ["orchestrator"]="orchestrator/cloudbuild.yaml"
  ["frontend"]="frontend/cloudbuild.yaml"
)

for SERVICE in "${!SERVICES[@]}"; do
  BUILD_CONFIG="${SERVICES[$SERVICE]}"
  TRIGGER_NAME="portfolio-copilot-${SERVICE}-tag"

  if gcloud builds triggers describe "$TRIGGER_NAME" \
       --project="$PROJECT_ID" --region="$REGION" &>/dev/null; then
    echo "Trigger $TRIGGER_NAME already exists — skipping."
    continue
  fi

  echo "Creating trigger $TRIGGER_NAME (config: $BUILD_CONFIG)..."
  gcloud builds triggers create github \
    --name="$TRIGGER_NAME" \
    --repository="$REPO_RESOURCE" \
    --tag-pattern="$TAG_PATTERN" \
    --build-config="$BUILD_CONFIG" \
    --substitutions="_REGION=${REGION},_AR_REPO=${AR_REPO}" \
    --project="$PROJECT_ID" \
    --region="$REGION"
done

echo ""
echo "========================================"
echo "Cloud Build triggers ready."
echo "Push a tag (e.g. 'git tag v0.1.0 && git push origin v0.1.0')"
echo "to build and deploy both services."
echo ""
echo "For manual builds without a tag, use the per-service Makefiles:"
echo "  make -C orchestrator deploy"
echo "  make -C frontend deploy"
echo "========================================"
