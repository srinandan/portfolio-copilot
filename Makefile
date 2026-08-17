GOOGLE_CLOUD_PROJECT ?= $(shell gcloud config get-value project 2>/dev/null)
GOOGLE_CLOUD_LOCATION ?= $(shell gcloud config get-value compute/region 2>/dev/null)
ifeq ($(GOOGLE_CLOUD_LOCATION),)
  GOOGLE_CLOUD_LOCATION := us-central1
endif
AGENT_REGISTRY_LOCATION ?= global
_COMMIT_SHA ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo local)

# Propagate these to the delegated per-service Makefiles (orchestrator/, frontend/)
# so `make deploy` reuses the values computed here — including the us-central1
# fallback and _COMMIT_SHA — instead of each sub-make recomputing them. Without
# this a delegated deploy with no gcloud compute/region configured would get an
# empty --region.
export GOOGLE_CLOUD_PROJECT GOOGLE_CLOUD_LOCATION AGENT_REGISTRY_LOCATION _COMMIT_SHA

.PHONY: help install deploy deploy-orchestrator deploy-frontend deploy-managed-agent register-skills setup-agent-engine setup-model-armor setup-all load-testdata local-orchestrator local-frontend local-server local-ui test test-orchestrator test-go test-frontend lint clean

help:
	@echo "Portfolio Copilot Makefile"
	@echo "--------------------------"
	@echo "Local Development:"
	@echo "  make install                  - Install all Python and frontend dependencies"
	@echo "  make local-orchestrator       - Run Python ADK orchestrator locally on :8000"
	@echo "  make local-frontend           - Run Vue Vite dev server with hot reload on :5173"
	@echo "  make local-server             - Build SPA & run Go backend server on :8080"
	@echo ""
	@echo "Testing & Linting:"
	@echo "  make test                     - Run test suites across Python, Go, and Vue"
	@echo "  make lint                     - Run linters across Python and Go"
	@echo ""
	@echo "Cloud Deployment:"
	@echo "  make deploy                   - Deploy full stack (orchestrator + frontend)"
	@echo "  make deploy-orchestrator      - Deploy orchestrator container to Vertex AI Agent Runtime"
	@echo "  make deploy-frontend          - Deploy frontend & Go server to Cloud Run"
	@echo "  make deploy-managed-agent     - Provision worker Managed Agent in Vertex AI"
	@echo "  make register-skills          - Register all runtime skills in Agent Registry"
	@echo ""
	@echo "Infra Provisioning & Test Data:"
	@echo "  make setup-agent-engine       - Setup Agent Runtime IAM, APIs, and permissions"
	@echo "  make setup-model-armor        - Configure Google Cloud Model Armor floor settings"
	@echo "  make setup-all                - End-to-end infra & services setup (setup_all.sh)"
	@echo "  make load-testdata            - Seed BigQuery and Firestore with canonical test data"
	@echo ""
	@echo "Teardown:"
	@echo "  make clean                    - DELETE the deployed orchestrator Agent Engine(s) in GCP"

install:
	cd frontend && npm ci
	cd orchestrator && uv sync

local-orchestrator:
	PORT=8000 $(MAKE) -C orchestrator local

local-frontend:
	$(MAKE) -C frontend local

local-ui: local-frontend

local-server:
	$(MAKE) -C frontend local-server

deploy-orchestrator:
	$(MAKE) -C orchestrator deploy

deploy-frontend:
	$(MAKE) -C frontend deploy

deploy: deploy-orchestrator deploy-frontend

deploy-managed-agent:
	./scripts/setup_managed_agent.sh "$(GOOGLE_CLOUD_PROJECT)" "$(GOOGLE_CLOUD_LOCATION)"

register-skills:
	./scripts/register_all_skills.sh "$(GOOGLE_CLOUD_PROJECT)" "$(AGENT_REGISTRY_LOCATION)"

setup-agent-engine:
	./scripts/setup_agent_engine.sh "$(GOOGLE_CLOUD_PROJECT)" "$(GOOGLE_CLOUD_LOCATION)"

setup-model-armor:
	./infra/setup_model_armor.sh "$(GOOGLE_CLOUD_PROJECT)"

setup-all:
	./scripts/setup_all.sh "$(GOOGLE_CLOUD_PROJECT)" "$(GOOGLE_CLOUD_LOCATION)"

load-testdata:
	./scripts/load_test_data.sh "$(GOOGLE_CLOUD_PROJECT)" "$(GOOGLE_CLOUD_LOCATION)"

test-orchestrator:
	$(MAKE) -C orchestrator test

# frontend/server's Go tests run under `test-frontend`; scope this to the shared
# Go libraries (pkg/...) so `make test` doesn't compile and run frontend/server twice.
test-go:
	go test ./pkg/... -cover

test-frontend:
	$(MAKE) -C frontend test

test: test-orchestrator test-go test-frontend

lint:
	$(MAKE) -C orchestrator lint
	go vet ./...

clean:
	$(MAKE) -C orchestrator clean
