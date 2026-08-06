GOOGLE_CLOUD_PROJECT ?= $(shell gcloud config get-value project)
PROJECT_NUMBER ?= $(shell gcloud projects describe ${GOOGLE_CLOUD_PROJECT} --format="value(projectNumber)")
GOOGLE_CLOUD_LOCATION ?= $(shell gcloud config get-value compute/region)
SERVICE_ACCOUNT_EMAIL ?= $(shell echo "portfolio-copilot-frontend-sa@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com")
_COMMIT_SHA ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo local)

.PHONY: local local-server deploy clean test test-ui test-server build install

install:
	npm ci

# `make local` runs the Vite dev server with hot reload during UI work.
# Vite's dev proxy (vite.config.ts) forwards /api and /health to
# http://localhost:8080 (matching `make local-server`).
local: install
	export _COMMIT_SHA=${_COMMIT_SHA} ;\
	export GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT} ;\
	export GOOGLE_CLOUD_PROJECT_NUMBER=${PROJECT_NUMBER} ;\
	export GOOGLE_CLOUD_REGION=${GOOGLE_CLOUD_LOCATION} ;\
	npm run dev

# `make local-server` builds the SPA and runs the Go backend server on port 8080
# (serving both static assets and API routes — the exact production container entrypoint).
local-server: build
	cd .. && STATIC_DIR=frontend/dist PORT=8080 go run ./frontend/server

build: install
	npm run build

test-ui: install
	npm run test

test-server:
	cd .. && go test ./frontend/server/...

test: test-ui test-server

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
	rm -rf dist node_modules
