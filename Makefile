GOOGLE_CLOUD_PROJECT ?= $(shell gcloud config get-value project 2>/dev/null)
GOOGLE_CLOUD_LOCATION ?= $(shell gcloud config get-value compute/region 2>/dev/null)
ifeq ($(GOOGLE_CLOUD_LOCATION),)
  GOOGLE_CLOUD_LOCATION := us-central1
endif
AGENT_REGISTRY_LOCATION ?= global
_COMMIT_SHA ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo local)

.PHONY: help deploy deploy-orchestrator deploy-frontend deploy-managed-agent register-skills setup-agent-engine setup-all load-testdata test test-orchestrator test-go test-frontend lint clean

help:
	@echo "Portfolio Copilot Makefile"
	@echo "--------------------------"
	@echo "make deploy               - Deploy full stack (orchestrator + frontend)"
	@echo "make deploy-orchestrator  - Deploy orchestrator container to Vertex AI Agent Runtime"
	@echo "make deploy-frontend      - Deploy frontend & Go server to Cloud Run"
	@echo "make deploy-managed-agent - Provision worker Managed Agent in Vertex AI"
	@echo "make register-skills      - Register all runtime skills in Agent Registry"
	@echo "make setup-agent-engine   - Setup Agent Runtime IAM, APIs, and permissions"
	@echo "make setup-all            - End-to-end infra & services setup (setup_all.sh)"
	@echo "make load-testdata        - Seed BigQuery and Firestore with canonical test data"
	@echo "make test                 - Run test suites across Python, Go, and Vue"
	@echo "make lint                 - Run linters across Python and Go"

deploy-orchestrator:
	$(MAKE) -C orchestrator deploy

deploy-frontend:
	$(MAKE) -C frontend deploy

deploy: deploy-orchestrator deploy-frontend

deploy-managed-agent:
	./scripts/setup_managed_agent.sh $(GOOGLE_CLOUD_PROJECT) $(GOOGLE_CLOUD_LOCATION)

register-skills:
	./scripts/register_all_skills.sh $(GOOGLE_CLOUD_PROJECT) $(AGENT_REGISTRY_LOCATION)

setup-agent-engine:
	./scripts/setup_agent_engine.sh $(GOOGLE_CLOUD_PROJECT) $(GOOGLE_CLOUD_LOCATION)

setup-all:
	./scripts/setup_all.sh $(GOOGLE_CLOUD_PROJECT) $(GOOGLE_CLOUD_LOCATION)

load-testdata:
	./scripts/load_test_data.sh $(GOOGLE_CLOUD_PROJECT) $(GOOGLE_CLOUD_LOCATION)

test-orchestrator:
	$(MAKE) -C orchestrator test

test-go:
	go test ./... -cover

test-frontend:
	$(MAKE) -C frontend test

test: test-orchestrator test-go test-frontend

lint:
	$(MAKE) -C orchestrator lint

clean:
	$(MAKE) -C orchestrator clean
	$(MAKE) -C frontend clean
