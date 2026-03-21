"""API smoke tests for health and basic wiring."""

from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.main import app


def test_api_healthcheck() -> None:
    """Health endpoint should return service-ready status."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["status"] == "ok"
    assert body["errors"] is None
