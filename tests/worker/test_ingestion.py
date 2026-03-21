"""Worker ingestion task tests for idempotency and deduplication."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from apps.api.models.patient_review import PatientReview
from apps.api.models.social_mention import SocialMention
from apps.worker.tasks import ingestion


@pytest.fixture
def worker_task_overrides(async_db_session, monkeypatch):
    """Patch worker task utilities to use test DB and skip Redis progress writes."""

    @asynccontextmanager
    async def _db_session():
        yield async_db_session

    async def _noop_progress(_task_id: str, _progress: int) -> None:
        return None

    monkeypatch.setattr(ingestion, "db_session", _db_session)
    monkeypatch.setattr(ingestion, "set_job_progress", _noop_progress)


@pytest.mark.asyncio
async def test_openfda_idempotency(worker_task_overrides, test_org_factory, test_drug_factory, httpx_mock, async_db_session) -> None:
    org = await test_org_factory(name="FDA Org", slug="fda-org")
    drug = await test_drug_factory(organization=org, name="IdemDrug")

    payload = {
        "results": [
            {
                "safetyreportid": "rpt-1",
                "receivedate": "20260320",
                "patient": {"reaction": [{"reactionmeddrapt": "nausea", "reactionoutcome": "3"}]},
            }
        ]
    }
    httpx_mock.add_response(url="https://api.fda.gov/drug/event.json", json=payload)
    httpx_mock.add_response(url="https://api.fda.gov/drug/event.json", json={"results": []})

    await ingestion.ingest_openfda.run("IdemDrug", str(org.id), str(drug.id))

    first_count = (
        await async_db_session.execute(select(func.count(PatientReview.id)).where(PatientReview.drug_id == drug.id))
    ).scalar_one()
    assert first_count == 1

    httpx_mock.add_response(url="https://api.fda.gov/drug/event.json", json=payload)
    httpx_mock.add_response(url="https://api.fda.gov/drug/event.json", json={"results": []})

    await ingestion.ingest_openfda.run("IdemDrug", str(org.id), str(drug.id))
    second_count = (
        await async_db_session.execute(select(func.count(PatientReview.id)).where(PatientReview.drug_id == drug.id))
    ).scalar_one()
    assert second_count == 1


@pytest.mark.asyncio
async def test_openfda_handles_empty_results(worker_task_overrides, test_org_factory, test_drug_factory, httpx_mock, async_db_session) -> None:
    org = await test_org_factory(name="Empty Org", slug="empty-org")
    drug = await test_drug_factory(organization=org, name="xyznotarealdrug123")

    httpx_mock.add_response(url="https://api.fda.gov/drug/event.json", status_code=404, json={})

    result = await ingestion.ingest_openfda.run("xyznotarealdrug123", str(org.id), str(drug.id))
    assert result["created"] == 0

    count = (
        await async_db_session.execute(select(func.count(PatientReview.id)).where(PatientReview.drug_id == drug.id))
    ).scalar_one()
    assert count == 0


@pytest.mark.asyncio
async def test_reddit_deduplication(worker_task_overrides, test_org_factory, test_drug_factory, async_db_session, monkeypatch) -> None:
    org = await test_org_factory(name="Reddit Org", slug="reddit-org")
    drug = await test_drug_factory(organization=org, name="DupDrug")

    class FakeAuthor:
        def __str__(self) -> str:
            return "demo-author"

    class FakeComments:
        async def replace_more(self, limit: int = 0) -> None:
            del limit
            return None

        def __iter__(self):
            return iter([])

    class FakeSubmission:
        def __init__(self, external_id: str) -> None:
            self.id = external_id
            self.title = "DupDrug works"
            self.selftext = "DupDrug mention"
            self.author = FakeAuthor()
            self.permalink = "/r/pharmacy/dup"
            self.created_utc = datetime.now(UTC).timestamp()
            self.score = 10
            self.comments = FakeComments()

    class FakeSubreddit:
        async def search(self, _query: str, limit: int = 50, sort: str = "new"):
            del limit, sort
            yield FakeSubmission("dup-post")
            yield FakeSubmission("dup-post")

    class FakeReddit:
        async def subreddit(self, _name: str):
            return FakeSubreddit()

        async def close(self):
            return None

    monkeypatch.setattr(ingestion.asyncpraw, "Reddit", lambda **_kwargs: FakeReddit())

    await ingestion.ingest_reddit.run("DupDrug", str(org.id), str(drug.id))

    count = (
        await async_db_session.execute(select(func.count(SocialMention.id)).where(SocialMention.drug_id == drug.id))
    ).scalar_one()
    assert count == 1
