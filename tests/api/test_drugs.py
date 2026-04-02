"""Drug CRUD, pagination, and async analysis job API tests."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest
from freezegun import freeze_time
from sqlalchemy import select

from apps.api.models.analysis_job import AnalysisJob
from apps.api.models.base import UserRole
from apps.api.models.drug import Drug


@pytest.mark.asyncio
async def test_cursor_pagination_is_consistent(
    test_client,
    test_user_factory,
    test_drug_factory,
    test_org_factory,
    auth_header,
) -> None:
    org = await test_org_factory(name="Pagination Org")
    user = await test_user_factory(role=UserRole.VIEWER, organization=org, email="pagination@example.com")
    for idx in range(25):
        await test_drug_factory(name=f"Drug-{idx:02d}", organization=org)

    seen: set[str] = set()
    cursor = None

    for _ in range(3):
        suffix = f"?limit=10&cursor={cursor}" if cursor else "?limit=10"
        response = await test_client.get(f"/drugs{suffix}", headers=auth_header(user))
        assert response.status_code == 200
        body = response.json()["data"]
        for item in body["items"]:
            assert item["id"] not in seen
            seen.add(item["id"])
        cursor = body["next_cursor"]
        if not cursor:
            break

    assert len(seen) == 25


@pytest.mark.asyncio
async def test_soft_delete_hides_drug(test_client, test_user_factory, test_drug_factory, auth_header, async_db_session) -> None:
    admin = await test_user_factory(role=UserRole.ADMIN, email="admin-delete@example.com")
    drug = await test_drug_factory(name="ToDelete")

    delete_response = await test_client.delete(f"/drugs/{drug.id}", headers=auth_header(admin))
    assert delete_response.status_code == 200

    list_response = await test_client.get("/drugs", headers=auth_header(admin))
    assert list_response.status_code == 200
    ids = [item["id"] for item in list_response.json()["data"]["items"]]
    assert str(drug.id) not in ids

    db_drug = (await async_db_session.execute(select(Drug).where(Drug.id == drug.id))).scalar_one()
    assert db_drug.deleted_at is not None


@pytest.mark.asyncio
async def test_analyze_job_returns_job_id(test_client, test_user_factory, test_drug_factory, auth_header, monkeypatch) -> None:
    analyst = await test_user_factory(role=UserRole.ANALYST, email="analyst-analyze@example.com")
    drug = await test_drug_factory(name="AnalyzeTarget")

    from apps.api.services import drug_service as drug_service_module

    monkeypatch.setattr(
        drug_service_module.celery_app,
        "send_task",
        lambda *args, **kwargs: SimpleNamespace(id="task-123"),
    )

    response = await test_client.post(f"/drugs/{drug.id}/analyze", headers=auth_header(analyst))
    assert response.status_code == 202
    body = response.json()["data"]
    UUID(body["job_id"])


@pytest.mark.asyncio
@freeze_time("2026-03-21 10:00:00")
async def test_poll_job_until_complete(test_client, test_user_factory, test_drug_factory, auth_header, monkeypatch, async_db_session) -> None:
    analyst = await test_user_factory(role=UserRole.ANALYST, email="poll-analyst@example.com")
    drug = await test_drug_factory(name="PollTarget")

    from apps.api.services import drug_service as drug_service_module

    monkeypatch.setattr(
        drug_service_module.celery_app,
        "send_task",
        lambda *args, **kwargs: SimpleNamespace(id="task-poll-1"),
    )

    trigger = await test_client.post(f"/drugs/{drug.id}/analyze", headers=auth_header(analyst))
    assert trigger.status_code == 202
    job_id = trigger.json()["data"]["job_id"]

    states = iter([
        ("PENDING", {}),
        ("STARTED", {"progress": 45}),
        ("SUCCESS", {"report_id": "abc-report", "status": "complete"}),
    ])

    class FakeAsyncResult:
        def __init__(self, *_args, **_kwargs):
            state, result = next(states)
            self.state = state
            self.result = result

    monkeypatch.setattr(drug_service_module, "AsyncResult", FakeAsyncResult)

    final_payload = None
    for _ in range(3):
        response = await test_client.get(f"/drugs/{drug.id}/analyze/{job_id}", headers=auth_header(analyst))
        assert response.status_code == 200
        payload = response.json()["data"]
        final_payload = payload
        if payload["status"] == "SUCCESS":
            break

    assert final_payload is not None
    assert final_payload["result_payload"]["report_id"] == "abc-report"

    db_job = (await async_db_session.execute(select(AnalysisJob).where(AnalysisJob.id == UUID(job_id)))).scalar_one()
    assert db_job.status == "SUCCESS"
