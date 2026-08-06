GOOGLE_CLOUD_PROJECT ?= $(shell gcloud config get-value project)
PROJECT_NUMBER ?= $(shell gcloud projects describe ${GOOGLE_CLOUD_PROJECT} --format="value(projectNumber)")
GOOGLE_CLOUD_LOCATION ?= $(shell gcloud config get-value compute/region)
SERVICE_ACCOUNT_EMAIL ?= $(shell echo "portfolio-copilot-frontend-sa@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com")
_COMMIT_SHA ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo local)

.PHONY: local local-server deploy clean test build install

install:
	npm ci

# `make local` runs the Vite dev server for hot reload during UI work.
# Vite's dev proxy (vite.config.ts) forwards /api and /health to
# GATEWAY_URL (default http://localhost:8080 — matches `make -C gateway local`).
local: install
	export _COMMIT_SHA=${_COMMIT_SHA} ;\
	export GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT} ;\
	export GOOGLE_CLOUD_PROJECT_NUMBER=${PROJECT_NUMBER} ;\
	export GOOGLE_CLOUD_REGION=${GOOGLE_CLOUD_LOCATION} ;\
	npm run dev

# `make local-server` builds the SPA and runs the production Go server
# (the same binary the container ships) — useful for smoke-testing the
# authed proxy path against a local gateway before deploying.
local-server: build
	cd .. && GATEWAY_URL=$${GATEWAY_URL:-http://localhost:8080} \
	  STATIC_DIR=$(CURDIR)/dist \
	  PORT=$${PORT:-8081} \
	  go run ./frontend/server

build: install
	npm run build

test: install
	npm run test

deploy:
	export _COMMIT_SHA=${_COMMIT_SHA} ;\
	export REGION=${GOOGLE_CLOUD_LOCATION} ;\
	export PROJECT_ID=${GOOGLE_CLOUD_PROJECT} ;\
	export PROJECT_NUMBER=${PROJECT_NUMBER} ;\
	cd .. && gcloud builds submit \
	  --config=frontend/cloudbuild.yaml \
	  --region=${GOOGLE_CLOUD_LOCATION} \
	  --substitutions=_COMMIT_SHA=${_COMMIT_SHA},_REGION=${GOOGLE_CLOUD_LOCATION}

clean:
	gcloud run services delete portfolio-copilot-frontend \
	  --region=${GOOGLE_CLOUD_LOCATION} \
	  --project=${GOOGLE_CLOUD_PROJECT} \
	  --quiet
