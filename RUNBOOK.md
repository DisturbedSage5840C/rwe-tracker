# RWE Tracker Production Runbook

## Services
- API: GCP Cloud Run service named rwe-api
- NLP: GCP Cloud Run service named rwe-nlp
- Worker batch: GCP Cloud Run Jobs (ingestion and migration jobs)
- Database: Cloud SQL PostgreSQL 16 with pgvector
- Cache/queue: Memorystore Redis 7
- Frontend: Vercel production deployment

## Roll Back a Bad Deployment
1. Identify the previous known-good image SHA.
2. Redeploy the API service using that SHA:
   - gcloud run deploy rwe-api --image=us-central1-docker.pkg.dev/PROJECT/rwe-tracker/api:PREVIOUS_SHA --region=us-central1 --platform=managed
3. Redeploy NLP if needed:
   - gcloud run deploy rwe-nlp --image=us-central1-docker.pkg.dev/PROJECT/rwe-tracker/nlp:PREVIOUS_SHA --region=us-central1 --platform=managed
4. Confirm health:
   - curl -fsS https://API_URL/health
   - curl -fsS https://NLP_URL/health
5. If the incident included schema drift, execute migration rollback plan manually before restoring traffic.

## Connect to Production Database
1. Start Cloud SQL Proxy:
   - cloud-sql-proxy PROJECT:us-central1:rwe-postgres16 --port 5432
2. Open psql in another terminal:
   - PGPASSWORD=DB_PASSWORD psql "host=127.0.0.1 port=5432 dbname=rwe_tracker user=rwe_app sslmode=disable"
3. Verify extension status:
   - SELECT extname FROM pg_extension WHERE extname = 'vector';

## View Live Logs
1. Recent API revision logs:
   - gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=rwe-api" --limit=100 --format=json | jq .
2. Recent NLP revision logs:
   - gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=rwe-nlp" --limit=100 --format=json | jq .
3. Cloud Run Job logs (worker/migrations):
   - gcloud logging read "resource.type=cloud_run_job" --limit=100 --format=json | jq .

## Scale Workers Up or Down Manually
Cloud Run Jobs do not autoscale the same way services do; scaling means adjusting execution parallelism and task count.

1. Increase worker job parallelism:
   - gcloud run jobs update rwe-worker --region=us-central1 --tasks=8 --parallelism=8
2. Decrease worker job parallelism:
   - gcloud run jobs update rwe-worker --region=us-central1 --tasks=2 --parallelism=2
3. Trigger a run immediately:
   - gcloud run jobs execute rwe-worker --region=us-central1 --wait

## Secret Rotation
1. Add a new secret version:
   - printf '%s' "NEW_VALUE" | gcloud secrets versions add SECRET_NAME --data-file=-
2. Redeploy affected Cloud Run service/job so latest secret version is mounted.
3. Validate service health and key dependent paths.
