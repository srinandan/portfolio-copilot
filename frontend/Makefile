GOOGLE_CLOUD_PROJECT ?= $(shell gcloud config get-value project)
PROJECT_NUMBER ?= $(shell gcloud projects describe ${GOOGLE_CLOUD_PROJECT} --format="value(projectNumber)")
GOOGLE_CLOUD_LOCATION ?= $(shell gcloud config get-value compute/region)
_COMMIT_SHA ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo local)

.PHONY: local deploy clean test build install

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
	export VITE_GATEWAY_URL=$${VITE_GATEWAY_URL:-$${GATEWAY_URL}} ;\
	npm run dev

build: install
	npm run build

test: install
	npm run test

deploy:
	$(MAKE) -C ../gateway deploy

clean:
	rm -rf dist node_modules
