#!/usr/bin/env bash
set -euo pipefail

# Idempotent GCP bootstrap for RWE Tracker production platform.

PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-us-central1}"
ZONE="${ZONE:-us-central1-a}"
ARTIFACT_REPO="${ARTIFACT_REPO:-rwe-tracker}"
SQL_INSTANCE="${SQL_INSTANCE:-rwe-postgres16}"
# Bootstrap tier is db-g1-small; set SQL_TIER=db-custom-2-7680 for production workloads.
SQL_TIER="${SQL_TIER:-db-g1-small}"
SQL_DB_NAME="${SQL_DB_NAME:-rwe_tracker}"
SQL_USER="${SQL_USER:-rwe_app}"
REDIS_INSTANCE="${REDIS_INSTANCE:-rwe-redis}"
REDIS_SIZE_GB="${REDIS_SIZE_GB:-1}"
SERVICE_ACCOUNT_NAME="${SERVICE_ACCOUNT_NAME:-rwe-runtime}"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
WIF_POOL_ID="${WIF_POOL_ID:-github-pool}"
WIF_PROVIDER_ID="${WIF_PROVIDER_ID:-github-provider}"
GITHUB_ORG="${GITHUB_ORG:-}"
GITHUB_REPO="${GITHUB_REPO:-}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "PROJECT_ID is required"
  exit 1
fi

if [[ -z "${GITHUB_ORG}" || -z "${GITHUB_REPO}" ]]; then
  echo "GITHUB_ORG and GITHUB_REPO are required"
  exit 1
fi

# Ensure CLI is targeting the right project for all subsequent idempotent operations.
gcloud config set project "${PROJECT_ID}" >/dev/null

# Enable all required managed service APIs used by Cloud Run, Cloud SQL, Redis, images, and secrets.
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  redis.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  --project "${PROJECT_ID}"

# Create Artifact Registry docker repo if missing to store immutable image revisions.
gcloud artifacts repositories describe "${ARTIFACT_REPO}" \
  --location "${REGION}" \
  --project "${PROJECT_ID}" >/dev/null 2>&1 || \
gcloud artifacts repositories create "${ARTIFACT_REPO}" \
  --location "${REGION}" \
  --repository-format docker \
  --description "RWE Tracker container images" \
  --project "${PROJECT_ID}"

# Create Cloud SQL Postgres 16 instance; small default tier for bootstrap (upgrade for production workloads).
gcloud sql instances describe "${SQL_INSTANCE}" --project "${PROJECT_ID}" >/dev/null 2>&1 || \
gcloud sql instances create "${SQL_INSTANCE}" \
  --database-version=POSTGRES_16 \
  --tier="${SQL_TIER}" \
  --region="${REGION}" \
  --storage-type=SSD \
  --storage-size=50 \
  --availability-type=zonal \
  --project "${PROJECT_ID}"

# Create application database if it does not already exist.
gcloud sql databases describe "${SQL_DB_NAME}" --instance "${SQL_INSTANCE}" --project "${PROJECT_ID}" >/dev/null 2>&1 || \
gcloud sql databases create "${SQL_DB_NAME}" --instance "${SQL_INSTANCE}" --project "${PROJECT_ID}"

# Create DB user account if absent; password is supplied out-of-band via env var for security.
if [[ -n "${SQL_USER_PASSWORD:-}" ]]; then
  gcloud sql users describe "${SQL_USER}" --instance "${SQL_INSTANCE}" --project "${PROJECT_ID}" >/dev/null 2>&1 || \
  gcloud sql users create "${SQL_USER}" --instance "${SQL_INSTANCE}" --password "${SQL_USER_PASSWORD}" --project "${PROJECT_ID}"
fi

# Enable pgvector extension so embeddings can be stored and queried.
gcloud sql connect "${SQL_INSTANCE}" --user=postgres --project "${PROJECT_ID}" --quiet <<'SQL'
CREATE EXTENSION IF NOT EXISTS vector;
SQL

# Create Memorystore Redis instance for Celery broker/result storage if missing.
gcloud redis instances describe "${REDIS_INSTANCE}" --region "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1 || \
gcloud redis instances create "${REDIS_INSTANCE}" \
  --region="${REGION}" \
  --zone="${ZONE}" \
  --tier=BASIC \
  --size="${REDIS_SIZE_GB}" \
  --redis-version=redis_7_0 \
  --project "${PROJECT_ID}"

# Create runtime service account used by Cloud Run services/jobs (principle of least privilege).
gcloud iam service-accounts describe "${SERVICE_ACCOUNT_EMAIL}" --project "${PROJECT_ID}" >/dev/null 2>&1 || \
gcloud iam service-accounts create "${SERVICE_ACCOUNT_NAME}" \
  --display-name "RWE Runtime Service Account" \
  --project "${PROJECT_ID}"

# Grant Cloud SQL access for private DB connectivity from Cloud Run runtime.
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/cloudsql.client" >/dev/null

# Grant Secret Manager accessor role so runtime can read deployed secret versions.
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" >/dev/null

# Grant invoker role for service-to-service calls where required.
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/run.invoker" >/dev/null

# Create expected secrets if absent; values are provided from local env to avoid hardcoding plaintext in repo.
for secret_name in DATABASE_URL REDIS_URL SECRET_KEY OPENFDA_BASE_URL OPENAI_API_KEY NLP_SERVICE_URL; do
  gcloud secrets describe "${secret_name}" --project "${PROJECT_ID}" >/dev/null 2>&1 || \
  gcloud secrets create "${secret_name}" --replication-policy="automatic" --project "${PROJECT_ID}"

  if [[ -n "${!secret_name:-}" ]]; then
    printf '%s' "${!secret_name}" | gcloud secrets versions add "${secret_name}" --data-file=- --project "${PROJECT_ID}"
  fi
done

# Create Workload Identity Pool for GitHub Actions OIDC federation, replacing static key files.
gcloud iam workload-identity-pools describe "${WIF_POOL_ID}" \
  --location="global" \
  --project "${PROJECT_ID}" >/dev/null 2>&1 || \
gcloud iam workload-identity-pools create "${WIF_POOL_ID}" \
  --location="global" \
  --display-name="GitHub Actions Pool" \
  --project "${PROJECT_ID}"

# Create OIDC provider bound to GitHub issuer with repository-level attribute mapping and condition.
gcloud iam workload-identity-pools providers describe "${WIF_PROVIDER_ID}" \
  --location="global" \
  --workload-identity-pool="${WIF_POOL_ID}" \
  --project "${PROJECT_ID}" >/dev/null 2>&1 || \
gcloud iam workload-identity-pools providers create-oidc "${WIF_PROVIDER_ID}" \
  --location="global" \
  --workload-identity-pool="${WIF_POOL_ID}" \
  --display-name="GitHub OIDC Provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref,attribute.actor=assertion.actor" \
  --attribute-condition="assertion.repository=='${GITHUB_ORG}/${GITHUB_REPO}'" \
  --project "${PROJECT_ID}"

# Allow identities from this GitHub repo provider to impersonate the deploy service account.
gcloud iam service-accounts add-iam-policy-binding "${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')/locations/global/workloadIdentityPools/${WIF_POOL_ID}/attribute.repository/${GITHUB_ORG}/${GITHUB_REPO}" \
  --project "${PROJECT_ID}" >/dev/null

echo "GCP bootstrap complete."
echo "Artifact Registry: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}"
echo "Workload Identity Provider: projects/$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')/locations/global/workloadIdentityPools/${WIF_POOL_ID}/providers/${WIF_PROVIDER_ID}"
