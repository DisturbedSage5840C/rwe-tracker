# syntax=docker/dockerfile:1.7
# Worker image reuses the API runtime stage (same base deps) and layers worker-specific deps.

ARG API_RUNTIME_IMAGE=rwe-api-runtime:local
FROM ${API_RUNTIME_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

USER root
COPY apps/worker/requirements.txt /tmp/worker-requirements.txt
RUN pip install --no-cache-dir -r /tmp/worker-requirements.txt
COPY apps /app/apps
RUN chown -R appuser:appuser /app

USER appuser

CMD ["celery", "-A", "apps.worker.celery_app", "worker", "--loglevel=info", "--concurrency=4", "-Q", "ingestion,analysis,celery"]
