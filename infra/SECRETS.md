# RWE Perception Tracker Secrets Reference

Scope rule used for this document: only names explicitly referenced in [.github/workflows/ci.yml](.github/workflows/ci.yml), [.github/workflows/deploy.yml](.github/workflows/deploy.yml), [infra/setup_gcp.sh](infra/setup_gcp.sh), and [infra/docker-compose.yml](infra/docker-compose.yml).

## 1. GitHub Repository Secrets (Settings -> Secrets -> Actions)

| Secret Name | Where Set | Format / Example | Set By | Cloud Run Binding |
| --- | --- | --- | --- | --- |
| CODECOV_TOKEN (MEDIUM) | GitHub repository secret | <PLACEHOLDER_CODECOV_TOKEN>. Comment: Missing this prevents coverage upload in CI. | Repo admin / CI maintainer | N/A |
| GCP_WORKLOAD_IDENTITY_PROVIDER (HIGH) | GitHub repository secret | projects/<PROJECT_NUMBER>/locations/global/workloadIdentityPools/<POOL_ID>/providers/<PROVIDER_ID>. Comment: Missing this prevents OIDC auth to GCP in deploy workflow. | Platform admin | N/A |
| GCP_DEPLOYER_SERVICE_ACCOUNT (HIGH) | GitHub repository secret | <SERVICE_ACCOUNT_EMAIL>. Comment: Missing this prevents GitHub Actions from impersonating deployer identity. | Platform admin | N/A |
| GCP_PROJECT_ID (MEDIUM) | GitHub repository secret | <PROJECT_ID>. Comment: Missing this breaks Artifact Registry, Cloud Run, and gcloud target resolution. | Platform admin | N/A |
| VERCEL_TOKEN (HIGH) | GitHub repository secret | <PLACEHOLDER_VERCEL_TOKEN>. Comment: Missing this blocks production frontend deploy job. | Frontend platform owner | N/A |
| SLACK_WEBHOOK_URL (MEDIUM) | GitHub repository secret | <PLACEHOLDER_SLACK_WEBHOOK_URL>. Comment: Missing this disables deployment notifications. | Ops / incident owner | N/A |

## 2. GCP Secret Manager Secrets (referenced in --set-secrets in deploy.yml)

| Secret Name | Where Set | Format / Example | Set By | Cloud Run Binding |
| --- | --- | --- | --- | --- |
| DATABASE_URL (CRITICAL) | GCP Secret Manager | postgresql+asyncpg://<DB_USER>:<DB_PASSWORD>@<DB_HOST>:5432/<DB_NAME>. Comment: Missing this prevents API and worker from connecting to PostgreSQL. | Platform admin via gcloud / Terraform | DATABASE_URL=DATABASE_URL:latest |
| REDIS_URL (HIGH) | GCP Secret Manager | redis://<REDIS_HOST>:6379/0. Comment: Missing this breaks Celery broker/result backend and cache paths. | Platform admin via gcloud / Terraform | REDIS_URL=REDIS_URL:latest |
| SECRET_KEY (CRITICAL) | GCP Secret Manager | <32+ random characters, high entropy>. Comment: Missing this breaks JWT signing/verification and invalidates auth flows. | Security owner / platform admin | SECRET_KEY=SECRET_KEY:latest |
| OPENFDA_BASE_URL (MEDIUM) | GCP Secret Manager | https://<OPENFDA_HOST>. Comment: Missing this breaks ingestion calls to openFDA. | Data ingestion owner | OPENFDA_BASE_URL=OPENFDA_BASE_URL:latest |
| OPENAI_API_KEY (CRITICAL) | GCP Secret Manager | <PLACEHOLDER_OPENAI_API_KEY>. Comment: Missing this breaks NLP enrichment/model calls that require provider auth. | AI platform owner | OPENAI_API_KEY=OPENAI_API_KEY:latest |
| NLP_SERVICE_URL (HIGH) | GCP Secret Manager | https://<NLP_CLOUD_RUN_URL>. Comment: Missing this prevents API/worker from calling NLP service endpoints. | Platform admin | NLP_SERVICE_URL=NLP_SERVICE_URL:latest |

Create commands for each Secret Manager secret:

gcloud secrets create DATABASE_URL --replication-policy="automatic" --project "<PROJECT_ID>"

gcloud secrets create REDIS_URL --replication-policy="automatic" --project "<PROJECT_ID>"

gcloud secrets create SECRET_KEY --replication-policy="automatic" --project "<PROJECT_ID>"

gcloud secrets create OPENFDA_BASE_URL --replication-policy="automatic" --project "<PROJECT_ID>"

gcloud secrets create OPENAI_API_KEY --replication-policy="automatic" --project "<PROJECT_ID>"

gcloud secrets create NLP_SERVICE_URL --replication-policy="automatic" --project "<PROJECT_ID>"

## 3. Local .env variables (referenced in docker-compose.yml)

| Secret Name | Where Set | Format / Example | Set By | Cloud Run Binding |
| --- | --- | --- | --- | --- |
| POSTGRES_DB (MEDIUM) | Local .env used by docker compose | <PLACEHOLDER_POSTGRES_DB>. Comment: Missing this causes database container init mismatch for expected DB name. | Developer (local machine) | N/A |
| POSTGRES_USER (MEDIUM) | Local .env used by docker compose | <PLACEHOLDER_POSTGRES_USER>. Comment: Missing this causes auth mismatch for local Postgres connections. | Developer (local machine) | N/A |
| POSTGRES_PASSWORD (HIGH) | Local .env used by docker compose | <PLACEHOLDER_POSTGRES_PASSWORD>. Comment: Missing this prevents local Postgres authentication and dependent services startup. | Developer (local machine) | N/A |
| REDIS_URL (HIGH) | Local .env used by docker compose | redis://<REDIS_HOST>:6379/0. Comment: Missing this breaks Flower broker wiring and local queue clients. | Developer (local machine) | N/A |
| FLOWER_BASIC_AUTH (MEDIUM) | Local .env used by docker compose | <USERNAME>:<PASSWORD>. Comment: Missing this falls back to default Flower credentials and weakens local security posture. | Developer (local machine) | N/A |

## 4. Cloud Run --set-secrets bindings (exact flag syntax for each deploy command)

Exact deploy-api syntax from [.github/workflows/deploy.yml](.github/workflows/deploy.yml):

--set-secrets="DATABASE_URL=DATABASE_URL:latest,REDIS_URL=REDIS_URL:latest,SECRET_KEY=SECRET_KEY:latest,OPENFDA_BASE_URL=OPENFDA_BASE_URL:latest,OPENAI_API_KEY=OPENAI_API_KEY:latest,NLP_SERVICE_URL=NLP_SERVICE_URL:latest"

Exact deploy-nlp syntax from [.github/workflows/deploy.yml](.github/workflows/deploy.yml):

--set-secrets="OPENAI_API_KEY=OPENAI_API_KEY:latest"

Exact deploy-worker syntax from [.github/workflows/deploy.yml](.github/workflows/deploy.yml):

--set-secrets="DATABASE_URL=DATABASE_URL:latest,REDIS_URL=REDIS_URL:latest,SECRET_KEY=SECRET_KEY:latest,OPENFDA_BASE_URL=OPENFDA_BASE_URL:latest,OPENAI_API_KEY=OPENAI_API_KEY:latest,NLP_SERVICE_URL=NLP_SERVICE_URL:latest"

| Secret Name | Where Set | Format / Example | Set By | Cloud Run Binding |
| --- | --- | --- | --- | --- |
| DATABASE_URL (CRITICAL) | deploy-api / deploy-worker Cloud Run deploy command | Secret Manager reference only. Comment: Missing this causes API/worker runtime DB outage. | GitHub Actions deploy workflow | DATABASE_URL=DATABASE_URL:latest |
| REDIS_URL (HIGH) | deploy-api / deploy-worker Cloud Run deploy command | Secret Manager reference only. Comment: Missing this breaks queue/cache connectivity. | GitHub Actions deploy workflow | REDIS_URL=REDIS_URL:latest |
| SECRET_KEY (CRITICAL) | deploy-api / deploy-worker Cloud Run deploy command | Secret Manager reference only, value must be 32+ random chars. Comment: Missing this breaks auth token trust. | GitHub Actions deploy workflow | SECRET_KEY=SECRET_KEY:latest |
| OPENFDA_BASE_URL (MEDIUM) | deploy-api / deploy-worker Cloud Run deploy command | Secret Manager reference only. Comment: Missing this breaks openFDA ingestion requests. | GitHub Actions deploy workflow | OPENFDA_BASE_URL=OPENFDA_BASE_URL:latest |
| OPENAI_API_KEY (CRITICAL) | deploy-api / deploy-nlp / deploy-worker Cloud Run deploy command | Secret Manager reference only. Comment: Missing this breaks provider-authorized NLP paths. | GitHub Actions deploy workflow | OPENAI_API_KEY=OPENAI_API_KEY:latest |
| NLP_SERVICE_URL (HIGH) | deploy-api / deploy-worker Cloud Run deploy command | Secret Manager reference only. Comment: Missing this blocks API/worker calls to NLP service. | GitHub Actions deploy workflow | NLP_SERVICE_URL=NLP_SERVICE_URL:latest |

## Secret Rotation

1. Create a new secret version in Secret Manager (do not overwrite existing versions).
2. Redeploy the affected Cloud Run service or job so a new revision is created with the same secret reference name at latest.
3. Keep the previous revision available during rollout; Cloud Run shifts traffic between revisions without stopping all instances at once.
4. Validate health and critical endpoints, then complete rollout.

Why this is no-downtime: Cloud Run revisions are immutable, and rolling traffic between old and new revisions allows instances with old and new secret versions to coexist during transition, avoiding hard cutover outages.
