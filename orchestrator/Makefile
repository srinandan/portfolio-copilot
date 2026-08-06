GOOGLE_CLOUD_PROJECT ?= $(shell gcloud config get-value project)
PROJECT_NUMBER ?= $(shell gcloud projects describe ${GOOGLE_CLOUD_PROJECT} --format="value(projectNumber)")
GOOGLE_CLOUD_LOCATION ?= $(shell gcloud config get-value compute/region)
SERVICE_ACCOUNT_EMAIL ?= $(shell echo "portfolio-copilot-orchestrator-sa@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com")
_COMMIT_SHA ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo local)

.PHONY: local deploy clean test lint

local:
	export _COMMIT_SHA=${_COMMIT_SHA} ;\
	export GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT} ;\
	export GOOGLE_CLOUD_PROJECT_NUMBER=${PROJECT_NUMBER} ;\
	export GOOGLE_CLOUD_REGION=${GOOGLE_CLOUD_LOCATION} ;\
	export SERVICE_ACCOUNT_EMAIL=${SERVICE_ACCOUNT_EMAIL} ;\
	export PYTHONPATH=src ;\
	export PORT=$${PORT:-8080} ;\
	uv sync && uv run uvicorn orchestrator.server:app --host 0.0.0.0 --port $${PORT}

test:
	uv run pytest

lint:
	uv run ruff check .

deploy:
	export _COMMIT_SHA=${_COMMIT_SHA} ;\
	export REGION=${GOOGLE_CLOUD_LOCATION} ;\
	export PROJECT_ID=${GOOGLE_CLOUD_PROJECT} ;\
	export PROJECT_NUMBER=${PROJECT_NUMBER} ;\
	cd .. && gcloud builds submit \
	  --config=orchestrator/cloudbuild.yaml \
	  --region=${GOOGLE_CLOUD_LOCATION} \
	  --substitutions=_COMMIT_SHA=${_COMMIT_SHA},_REGION=${GOOGLE_CLOUD_LOCATION}

clean:
	@echo "Deleting Agent Engine(s) with displayName=portfolio-copilot-agent in ${GOOGLE_CLOUD_LOCATION}..." ;\
	TOKEN=$$(gcloud auth print-access-token 2>/dev/null || echo "") ;\
	if [ -n "$$TOKEN" ]; then \
	  curl -s -H "Authorization: Bearer $$TOKEN" \
	    "https://${GOOGLE_CLOUD_LOCATION}-aiplatform.googleapis.com/v1beta1/projects/${GOOGLE_CLOUD_PROJECT}/locations/${GOOGLE_CLOUD_LOCATION}/reasoningEngines" \
	    | jq -r '.reasoningEngines[]? | select(.displayName == "portfolio-copilot-agent") | .name // empty' \
	    | while read ENGINE; do \
	        [ -z "$$ENGINE" ] && continue ;\
	        echo "Deleting $$ENGINE..." ;\
	        curl -s -X DELETE -H "Authorization: Bearer $$TOKEN" \
	          "https://${GOOGLE_CLOUD_LOCATION}-aiplatform.googleapis.com/v1beta1/$$ENGINE" ;\
	      done ;\
	fi
