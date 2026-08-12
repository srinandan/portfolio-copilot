GOOGLE_CLOUD_PROJECT ?= $(shell gcloud config get-value project)
GOOGLE_CLOUD_LOCATION ?= $(shell gcloud config get-value compute/region)
_COMMIT_SHA ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo local)

.PHONY: help deploy deploy-orchestrator deploy-frontend test test-orchestrator test-go test-frontend lint clean

help:
	@echo "Portfolio Copilot Makefile"
	@echo "--------------------------"
	@echo "make deploy               - Deploy both orchestrator and frontend"
	@echo "make deploy-orchestrator  - Deploy orchestrator to Vertex AI Agent Runtime"
	@echo "make deploy-frontend      - Deploy frontend to Cloud Run"
	@echo "make test                 - Run test suites across Python, Go, and Vue"
	@echo "make lint                 - Run linters across Python and Go"

deploy-orchestrator:
	$(MAKE) -C orchestrator deploy

deploy-frontend:
	$(MAKE) -C frontend deploy

deploy: deploy-orchestrator deploy-frontend

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
