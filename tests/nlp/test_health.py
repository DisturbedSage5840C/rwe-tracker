"""NLP service smoke tests for readiness."""

from __future__ import annotations

from fastapi.testclient import TestClient

from apps.nlp.main import app


def test_nlp_healthcheck() -> None:
    """NLP health endpoint should return service-ready status."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
