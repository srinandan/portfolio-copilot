GOOGLE_CLOUD_PROJECT ?= $(shell gcloud config get-value project)
PROJECT_NUMBER ?= $(shell gcloud projects describe ${GOOGLE_CLOUD_PROJECT} --format="value(projectNumber)")
GOOGLE_CLOUD_LOCATION ?= $(shell gcloud config get-value compute/region)
SERVICE_ACCOUNT_EMAIL ?= $(shell echo "portfolio-copilot-gateway-sa@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com")
_COMMIT_SHA ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo local)

.PHONY: local deploy clean test build

local:
	export _COMMIT_SHA=${_COMMIT_SHA} ;\
	export GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT} ;\
	export GOOGLE_CLOUD_PROJECT_NUMBER=${PROJECT_NUMBER} ;\
	export GOOGLE_CLOUD_REGION=${GOOGLE_CLOUD_LOCATION} ;\
	export SERVICE_ACCOUNT_EMAIL=${SERVICE_ACCOUNT_EMAIL} ;\
	cd .. && go mod tidy && go run ./gateway

build:
	cd .. && go build -o gateway/gateway-bin ./gateway

test:
	cd .. && go test ./gateway/...

deploy:
	export _COMMIT_SHA=${_COMMIT_SHA} ;\
	export REGION=${GOOGLE_CLOUD_LOCATION} ;\
	export PROJECT_ID=${GOOGLE_CLOUD_PROJECT} ;\
	export PROJECT_NUMBER=${PROJECT_NUMBER} ;\
	cd .. && gcloud builds submit \
	  --config=gateway/cloudbuild.yaml \
	  --region=${GOOGLE_CLOUD_LOCATION} \
	  --substitutions=_COMMIT_SHA=${_COMMIT_SHA},_REGION=${GOOGLE_CLOUD_LOCATION}

clean:
	gcloud run services delete portfolio-copilot-gateway \
	  --region=${GOOGLE_CLOUD_LOCATION} \
	  --project=${GOOGLE_CLOUD_PROJECT} \
	  --quiet
