# RWE Tracker

RWE Tracker is a real-world evidence perception platform for monitoring how drug experience in the real world compares with expected clinical outcomes.

The system ingests source evidence (OpenFDA, ClinicalTrials, Reddit), runs asynchronous NLP and gap analysis, and serves insights through a Next.js dashboard.

## Core Features

- Multi-tenant drug tracking with role-based access
- Async ingestion and analysis job orchestration (Celery + Redis)
- Per-drug perception reports with trend and gap dimensions
- Source transparency in report payloads via source_metrics
- Frontend dashboard with job progress polling and report visualization

## Architecture at a Glance

- Frontend: Next.js 14 (TypeScript, SWR, Zustand, Recharts)
- API: FastAPI + SQLAlchemy async + Alembic migrations
- NLP Service: FastAPI microservice with transformer-based sentiment pipeline
- Worker: Celery tasks for ingestion and analysis callback
- Database: PostgreSQL 16 (pgvector image used in local compose)
- Queue/Cache: Redis 7
- Local orchestration: Docker Compose

## Repository Structure

- apps/api: FastAPI app, routers, models, services, auth
- apps/worker: Celery app, ingestion tasks, analysis tasks
- apps/nlp: NLP microservice
- frontend: Next.js dashboard
- infra: Dockerfiles and docker-compose
- migrations: Alembic migration history
- tests: API/NLP/worker test suites

## Prerequisites

- Python 3.11+
- Node.js 18+
- Docker Desktop (or Docker Engine with Compose v2)
- npm

## Environment Setup

1. Copy env template:

   cp .env.example .env

2. Update required secrets in .env for your environment:

- SECRET_KEY
- OPENAI_API_KEY (if used by your pipelines)
- REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET (optional if fallback mode is acceptable)

## Quick Start (Recommended)

1. Start backend stack:

   docker compose -f infra/docker-compose.yml up --build -d

2. Apply database migrations:

   source .venv/bin/activate
   alembic upgrade head

3. Start frontend:

   cd frontend
   npm install
   npm run dev

4. Open application:

- Frontend: http://localhost:3000
- API health: http://localhost:8000/health
- Flower: http://localhost:5555

## Python Dependencies

Install service requirements (if running services outside containers):

- API: pip install -r apps/api/requirements.txt
- NLP: pip install -r apps/nlp/requirements.txt
- Worker: pip install -r apps/worker/requirements.txt

## Frontend Scripts

Run from frontend directory:

- npm run dev: start development server
- npm run build: production build
- npm run start: run production server
- npm run lint: lint checks
- npm run test: unit tests (Vitest)

## Makefile Commands

From repository root:

- make dev: compose up with build
- make build: build images
- make migrate: run Alembic migrations
- make lint: backend and frontend lint
- make test: backend and frontend tests

## Analysis Flow

1. User authenticates and creates/selects a drug.
2. API creates an analysis job.
3. Worker runs ingestion tasks:
   - ingestion.openfda
   - ingestion.reddit
   - ingestion.clinical_trials
4. Worker callback runs analysis and persists a perception report.
5. Frontend polls job status and renders trends, gaps, and insights.

## Troubleshooting

### API unhealthy

- Check compose status:

  docker compose -f infra/docker-compose.yml ps

- Check API logs:

  docker compose -f infra/docker-compose.yml logs --since=10m api

### Worker jobs stuck

- Check worker logs:

  docker compose -f infra/docker-compose.yml logs --since=10m worker

- Check Redis connectivity and Flower UI:

  docker compose -f infra/docker-compose.yml logs --since=10m redis

### Frontend cannot reach API

- Confirm NEXT_PUBLIC_API_BASE_URL in .env
- Confirm API is reachable at configured host/port

## Production Notes

See RUNBOOK.md for Cloud Run, Cloud SQL, rollback, logs, and secret rotation procedures.

## Documentation Artifacts

- RWE_Tracker_Documentation.html
- RWE_Tracker_Documentation.pdf

## License

Internal project. Add licensing terms before external distribution.
