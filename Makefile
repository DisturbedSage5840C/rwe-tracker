# Developer workflows for local orchestration and quality checks.

COMPOSE = docker compose -f infra/docker-compose.yml
GCP_REGION ?= us-central1
GCP_PROJECT ?=
ARTIFACT_REPO ?= rwe-tracker
API_SERVICE ?= rwe-api
SQL_INSTANCE ?= rwe-postgres16
SQL_DB_NAME ?= rwe_tracker
SQL_USER ?= rwe_app

.PHONY: dev test migrate lint build deploy-staging rollback logs-api db-connect secrets-sync

dev:
	$(COMPOSE) up --build

test:
	pytest tests -q
	cd frontend && npm run test

migrate:
	alembic upgrade head

lint:
	ruff check apps tests
	cd frontend && npm run lint

build:
	$(COMPOSE) build

deploy-staging:
	@if [ -z "$(GCP_PROJECT)" ]; then echo "Set GCP_PROJECT"; exit 1; fi
	@SHA=$$(git rev-parse --short=12 HEAD); \
	IMAGE="$(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT)/$(ARTIFACT_REPO)/api:$$SHA"; \
	gcloud run deploy "$(API_SERVICE)-staging" \
		--image="$$IMAGE" \
		--region="$(GCP_REGION)" \
		--platform=managed \
		--tag=staging \
		--set-secrets="DATABASE_URL=DATABASE_URL:latest,REDIS_URL=REDIS_URL:latest,SECRET_KEY=SECRET_KEY:latest" \
		--allow-unauthenticated

rollback:
	@if [ -z "$(GCP_PROJECT)" ]; then echo "Set GCP_PROJECT"; exit 1; fi
	@PREV_SHA=$$(git log --pretty=format:%H -n 2 | tail -n 1 | cut -c1-12); \
	if [ -z "$$PREV_SHA" ]; then echo "No previous commit SHA found"; exit 1; fi; \
	IMAGE="$(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT)/$(ARTIFACT_REPO)/api:$$PREV_SHA"; \
	gcloud run deploy "$(API_SERVICE)" --image="$$IMAGE" --region="$(GCP_REGION)" --platform=managed

logs-api:
	gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$(API_SERVICE)" --limit=100 --format=json | jq .

db-connect:
	@cloud-sql-proxy "$(GCP_PROJECT):$(GCP_REGION):$(SQL_INSTANCE)" --port 5432 & \
	PROXY_PID=$$!; \
	sleep 3; \
	PGPASSWORD="$$DB_PASSWORD" psql "host=127.0.0.1 port=5432 dbname=$(SQL_DB_NAME) user=$(SQL_USER) sslmode=disable"; \
	kill $$PROXY_PID

secrets-sync:
	@if [ -z "$(GCP_PROJECT)" ]; then echo "Set GCP_PROJECT"; exit 1; fi
	@{ \
		echo "DATABASE_URL=$$(gcloud secrets versions access latest --secret=DATABASE_URL --project=$(GCP_PROJECT))"; \
		echo "REDIS_URL=$$(gcloud secrets versions access latest --secret=REDIS_URL --project=$(GCP_PROJECT))"; \
		echo "SECRET_KEY=$$(gcloud secrets versions access latest --secret=SECRET_KEY --project=$(GCP_PROJECT))"; \
		echo "OPENFDA_BASE_URL=$$(gcloud secrets versions access latest --secret=OPENFDA_BASE_URL --project=$(GCP_PROJECT))"; \
		echo "OPENAI_API_KEY=$$(gcloud secrets versions access latest --secret=OPENAI_API_KEY --project=$(GCP_PROJECT))"; \
		echo "NLP_SERVICE_URL=$$(gcloud secrets versions access latest --secret=NLP_SERVICE_URL --project=$(GCP_PROJECT))"; \
	} > .env
