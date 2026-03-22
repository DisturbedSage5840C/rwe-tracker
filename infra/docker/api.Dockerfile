# syntax=docker/dockerfile:1.7
# API image kept lean (<500MB target) via multi-stage build and venv copy.

ARG PYTHON_IMAGE=python:3.11-slim

FROM ${PYTHON_IMAGE} AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV VENV_PATH=/opt/venv

WORKDIR /build

RUN apt-get update \
	&& apt-get install -y --no-install-recommends gcc build-essential curl \
	&& python -m venv ${VENV_PATH} \
	&& ${VENV_PATH}/bin/pip install --upgrade pip setuptools wheel \
	&& rm -rf /var/lib/apt/lists/*

# Copy requirements first to maximize layer cache hit rate.
COPY apps/api/requirements.txt /build/requirements.txt
RUN ${VENV_PATH}/bin/pip install --no-cache-dir -r /build/requirements.txt

FROM ${PYTHON_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV VENV_PATH=/opt/venv
ENV PATH="${VENV_PATH}/bin:${PATH}"

WORKDIR /app

RUN apt-get update \
	&& apt-get install -y --no-install-recommends curl \
	&& rm -rf /var/lib/apt/lists/* \
	&& groupadd --gid 10001 appuser \
	&& useradd --uid 10001 --gid appuser --create-home --shell /usr/sbin/nologin appuser

COPY --from=builder ${VENV_PATH} ${VENV_PATH}
COPY apps /app/apps
COPY alembic.ini /app/alembic.ini
COPY migrations /app/migrations

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=5 --start-period=20s CMD curl -f http://localhost:8080/health || exit 1

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2", "--no-access-log"]
