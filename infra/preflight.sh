#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: infra/preflight.sh [--dry-run] [--help]

Strict preflight validation for RWE Tracker GCP environment.

Options:
  --dry-run   Run all checks and print failures, but always exit 0.
  --help      Show this help message.

Environment variables:
  PROJECT_ID            Required target GCP project ID.
  REGION                GCP region for Redis and Artifact Registry checks. Default: us-central1
  ARTIFACT_REPO_NAME    Artifact Registry repo name. Default: rwe-tracker
  SQL_INSTANCE_NAME     Cloud SQL instance name. Default: rwe-postgres16
  SQL_DB_NAME           Cloud SQL database for extension check. Default: postgres
  SQL_DB_USER           Cloud SQL user for extension check. Default: postgres
  REDIS_INSTANCE_NAME   Memorystore Redis instance name. Default: rwe-redis
  SERVICE_ACCOUNT_EMAIL Service account to validate IAM roles.
  WIF_POOL_ID           Workload Identity Federation pool ID. Default: github-pool
  WIF_PROVIDER_ID       Workload Identity Federation provider ID. Default: github-provider
USAGE
}

# Defaults are set with := per requirement.
: "${PROJECT_ID:=}"
: "${REGION:=us-central1}"
: "${ARTIFACT_REPO_NAME:=rwe-tracker}"
: "${SQL_INSTANCE_NAME:=rwe-postgres16}"
: "${SQL_DB_NAME:=postgres}"
: "${SQL_DB_USER:=postgres}"
: "${REDIS_INSTANCE_NAME:=rwe-redis}"
: "${SERVICE_ACCOUNT_EMAIL:=}"
: "${WIF_POOL_ID:=github-pool}"
: "${WIF_PROVIDER_ID:=github-provider}"

DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run)
      DRY_RUN=1
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $arg"
      usage
      exit 1
      ;;
  esac
done

if command -v tput >/dev/null 2>&1; then
  GREEN="$(tput setaf 2)"
  RED="$(tput setaf 1)"
  RESET="$(tput sgr0)"
else
  GREEN=""
  RED=""
  RESET=""
fi

TOTAL_CHECKS=12
CHECKS_RUN=0
CHECKS_PASSED=0
FAILURES=0
GCLOUD_AVAILABLE=0

check_header() {
  CHECKS_RUN=$((CHECKS_RUN + 1))
  echo "[CHECK] Verifying $1..."
}

pass_check() {
  CHECKS_PASSED=$((CHECKS_PASSED + 1))
  echo "[PASS] $1"
}

fail_check() {
  FAILURES=$((FAILURES + 1))
  echo "[FAIL] $1"
  if [[ "$DRY_RUN" -eq 0 ]]; then
    echo "Summary: ${CHECKS_PASSED}/${CHECKS_RUN} checks passed."
    echo "${RED}Preflight failed. Fix the above errors before deploying.${RESET}"
    exit 1
  fi
}

# 1. gcloud CLI installed.
check_header "gcloud CLI installed"
if command -v gcloud >/dev/null 2>&1; then
  GCLOUD_AVAILABLE=1
  pass_check "gcloud CLI found"
else
  fail_check "gcloud is not installed or not in PATH"
fi

# 2. gcloud authenticated.
check_header "gcloud authenticated"
if [[ "$GCLOUD_AVAILABLE" -eq 0 ]]; then
  fail_check "cannot verify authentication because gcloud CLI is unavailable"
else
  ACCESS_TOKEN="$(gcloud auth print-access-token 2>/dev/null || true)"
  if [[ -n "$ACCESS_TOKEN" ]]; then
    pass_check "gcloud account has a valid access token"
  else
    fail_check "gcloud auth print-access-token returned empty; run gcloud auth login"
  fi
fi

# 3. PROJECT_ID env var set and non-empty.
check_header "PROJECT_ID env var set"
if [[ -n "$PROJECT_ID" ]]; then
  pass_check "PROJECT_ID is set to '$PROJECT_ID'"
else
  fail_check "PROJECT_ID is empty; export PROJECT_ID before deployment"
fi

# 4. Active gcloud project matches PROJECT_ID.
check_header "active gcloud project matches PROJECT_ID"
if [[ "$GCLOUD_AVAILABLE" -eq 0 ]]; then
  fail_check "cannot verify active project because gcloud CLI is unavailable"
else
  ACTIVE_PROJECT="$(gcloud config get-value project 2>/dev/null || true)"
  if [[ "$ACTIVE_PROJECT" == "$PROJECT_ID" && -n "$ACTIVE_PROJECT" ]]; then
    pass_check "active project matches PROJECT_ID"
  else
    fail_check "active gcloud project '$ACTIVE_PROJECT' does not match PROJECT_ID '$PROJECT_ID'"
  fi
fi

# 5. Required APIs enabled; check each individually and list missing.
check_header "required APIs are enabled"
if [[ "$GCLOUD_AVAILABLE" -eq 0 ]]; then
  fail_check "cannot verify APIs because gcloud CLI is unavailable"
else
  MISSING_APIS=()
  for api in \
    run.googleapis.com \
    sqladmin.googleapis.com \
    redis.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com \
    compute.googleapis.com; do
    # Validate a single API is enabled by querying enabled services for an exact name match.
    if ! gcloud services list --enabled --project "$PROJECT_ID" --filter="name=$api" --format="value(name)" | grep -qx "$api"; then
      MISSING_APIS+=("$api")
    fi
  done
  if [[ "${#MISSING_APIS[@]}" -eq 0 ]]; then
    pass_check "all required APIs are enabled"
  else
    fail_check "missing enabled APIs: ${MISSING_APIS[*]}"
  fi
fi

# 6. Artifact Registry repo exists.
check_header "Artifact Registry repo exists"
# Validate repo exists by describing the expected repository name in target region.
if [[ "$GCLOUD_AVAILABLE" -eq 0 ]]; then
  fail_check "cannot verify Artifact Registry because gcloud CLI is unavailable"
else
  if gcloud artifacts repositories describe "$ARTIFACT_REPO_NAME" --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1; then
    pass_check "Artifact Registry repo '$ARTIFACT_REPO_NAME' exists"
  else
    fail_check "Artifact Registry repo '$ARTIFACT_REPO_NAME' not found in region '$REGION'"
  fi
fi

# 7. Cloud SQL instance exists and is RUNNABLE.
check_header "Cloud SQL instance exists and is RUNNABLE"
# Validate Cloud SQL instance health state from control plane metadata.
if [[ "$GCLOUD_AVAILABLE" -eq 0 ]]; then
  fail_check "cannot verify Cloud SQL state because gcloud CLI is unavailable"
else
  SQL_STATE="$(gcloud sql instances describe "$SQL_INSTANCE_NAME" --project "$PROJECT_ID" --format="value(state)" 2>/dev/null || true)"
  if [[ "$SQL_STATE" == "RUNNABLE" ]]; then
    pass_check "Cloud SQL instance '$SQL_INSTANCE_NAME' is RUNNABLE"
  elif [[ -z "$SQL_STATE" ]]; then
    fail_check "Cloud SQL instance '$SQL_INSTANCE_NAME' not found"
  else
    fail_check "Cloud SQL instance '$SQL_INSTANCE_NAME' state is '$SQL_STATE' (expected RUNNABLE)"
  fi
fi

# 8. Cloud SQL has pgvector extension.
check_header "Cloud SQL has pgvector extension"
# Validate pgvector availability by running an extension query through gcloud sql connect.
if [[ "$GCLOUD_AVAILABLE" -eq 0 ]]; then
  fail_check "cannot verify pgvector extension because gcloud CLI is unavailable"
else
  VECTOR_OUTPUT="$({ printf "SELECT installed_version FROM pg_available_extensions WHERE name='vector';\\n"; printf "\\q\\n"; } | gcloud sql connect "$SQL_INSTANCE_NAME" --project "$PROJECT_ID" --user "$SQL_DB_USER" --database "$SQL_DB_NAME" --quiet 2>/dev/null || true)"
  if echo "$VECTOR_OUTPUT" | grep -Eq '[0-9]+(\.[0-9]+)*'; then
    pass_check "pgvector extension is available"
  else
    fail_check "pgvector extension query did not return a version; ensure vector extension is installed and accessible"
  fi
fi

# 9. Memorystore Redis instance exists and is READY.
check_header "Memorystore Redis instance exists and is READY"
# Validate Redis control-plane state to ensure instance is provisioned and ready for clients.
if [[ "$GCLOUD_AVAILABLE" -eq 0 ]]; then
  fail_check "cannot verify Memorystore Redis because gcloud CLI is unavailable"
else
  REDIS_STATE="$(gcloud redis instances describe "$REDIS_INSTANCE_NAME" --region "$REGION" --project "$PROJECT_ID" --format="value(state)" 2>/dev/null || true)"
  if [[ "$REDIS_STATE" == "READY" ]]; then
    pass_check "Redis instance '$REDIS_INSTANCE_NAME' is READY"
  elif [[ -z "$REDIS_STATE" ]]; then
    fail_check "Redis instance '$REDIS_INSTANCE_NAME' not found in region '$REGION'"
  else
    fail_check "Redis instance '$REDIS_INSTANCE_NAME' state is '$REDIS_STATE' (expected READY)"
  fi
fi

# 10. Required Secret Manager secrets exist; check each individually.
check_header "required Secret Manager secrets exist"
if [[ "$GCLOUD_AVAILABLE" -eq 0 ]]; then
  fail_check "cannot verify Secret Manager because gcloud CLI is unavailable"
else
  MISSING_SECRETS=()
  for secret_name in DATABASE_URL REDIS_URL SECRET_KEY NLP_SERVICE_URL OPENFDA_BASE_URL SENTRY_DSN; do
    # Validate each secret exists by metadata describe call in Secret Manager.
    if ! gcloud secrets describe "$secret_name" --project "$PROJECT_ID" >/dev/null 2>&1; then
      MISSING_SECRETS+=("$secret_name")
    fi
  done
  if [[ "${#MISSING_SECRETS[@]}" -eq 0 ]]; then
    pass_check "all required Secret Manager secrets are present"
  else
    fail_check "missing Secret Manager secrets: ${MISSING_SECRETS[*]}"
  fi
fi

# 11. Service account exists and has required roles.
check_header "service account exists and has required roles"
if [[ -z "$SERVICE_ACCOUNT_EMAIL" ]]; then
  fail_check "SERVICE_ACCOUNT_EMAIL is empty; cannot validate IAM role bindings"
elif [[ "$GCLOUD_AVAILABLE" -eq 0 ]]; then
  fail_check "cannot verify service account roles because gcloud CLI is unavailable"
else
  # Validate service account exists in IAM before role binding checks.
  if ! gcloud iam service-accounts describe "$SERVICE_ACCOUNT_EMAIL" --project "$PROJECT_ID" >/dev/null 2>&1; then
    fail_check "service account '$SERVICE_ACCOUNT_EMAIL' does not exist"
  else
    MISSING_ROLES=()
    for role in roles/run.invoker roles/cloudsql.client roles/secretmanager.secretAccessor; do
      # Validate each required role by reading project IAM policy bindings for this service account member.
      if ! gcloud projects get-iam-policy "$PROJECT_ID" \
        --flatten="bindings[].members" \
        --filter="bindings.members:serviceAccount:${SERVICE_ACCOUNT_EMAIL} AND bindings.role:${role}" \
        --format="value(bindings.role)" | grep -qx "$role"; then
        MISSING_ROLES+=("$role")
      fi
    done

    if [[ "${#MISSING_ROLES[@]}" -eq 0 ]]; then
      pass_check "service account has all required roles"
    else
      fail_check "service account '$SERVICE_ACCOUNT_EMAIL' missing roles: ${MISSING_ROLES[*]}"
    fi
  fi
fi

# 12. Workload Identity Federation pool and provider exist.
check_header "Workload Identity Federation pool and provider exist"
# Validate WIF pool exists in global location for GitHub OIDC federation.
if [[ "$GCLOUD_AVAILABLE" -eq 0 ]]; then
  fail_check "cannot verify Workload Identity Federation because gcloud CLI is unavailable"
else
  POOL_EXISTS=0
  PROVIDER_EXISTS=0
  if gcloud iam workload-identity-pools describe "$WIF_POOL_ID" --location="global" --project "$PROJECT_ID" >/dev/null 2>&1; then
    POOL_EXISTS=1
  fi
  # Validate WIF provider exists in selected pool and global location.
  if gcloud iam workload-identity-pools providers describe "$WIF_PROVIDER_ID" --location="global" --workload-identity-pool="$WIF_POOL_ID" --project "$PROJECT_ID" >/dev/null 2>&1; then
    PROVIDER_EXISTS=1
  fi

  if [[ "$POOL_EXISTS" -eq 1 && "$PROVIDER_EXISTS" -eq 1 ]]; then
    pass_check "WIF pool '$WIF_POOL_ID' and provider '$WIF_PROVIDER_ID' exist"
  else
    MSG=""
    if [[ "$POOL_EXISTS" -eq 0 ]]; then
      MSG="WIF pool '$WIF_POOL_ID' is missing"
    fi
    if [[ "$PROVIDER_EXISTS" -eq 0 ]]; then
      if [[ -n "$MSG" ]]; then
        MSG+="; "
      fi
      MSG+="WIF provider '$WIF_PROVIDER_ID' is missing"
    fi
    fail_check "$MSG"
  fi
fi

echo "Summary: ${CHECKS_PASSED}/${TOTAL_CHECKS} checks passed."
if [[ "$FAILURES" -eq 0 ]]; then
  echo "${GREEN}Preflight complete. Safe to deploy.${RESET}"
  exit 0
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "${RED}Preflight failed. Fix the above errors before deploying.${RESET}"
  exit 0
fi

echo "${RED}Preflight failed. Fix the above errors before deploying.${RESET}"
exit 1
