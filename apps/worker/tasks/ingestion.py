"""Celery ingestion tasks for openFDA, Reddit, and ClinicalTrials sources."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import asyncpraw
import asyncprawcore
import httpx
from celery import chord
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from apps.api.config import get_settings
from apps.api.models.clinical_trial import ClinicalTrial
from apps.api.models.patient_review import PatientReview
from apps.api.models.social_mention import SocialMention
from apps.common.logging import get_logger
from apps.worker.celery_app import celery_app
from apps.worker.tasks.utils import db_session, run_async, set_job_progress, with_retry

logger = get_logger(__name__)
settings = get_settings()

REDDIT_SUBREDDITS = [
    "pharmacy",
    "medicine",
    "diabetes",
    "depression",
    "anxiety",
    "ChronicPain",
    "MultipleSclerosis",
    "rheumatoid",
]


def _parse_fda_date(value: str | None) -> datetime | None:
    """Parse OpenFDA YYYYMMDD strings to UTC datetimes."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y%m%d").replace(tzinfo=UTC)
    except ValueError:
        return None


def _derive_openfda_sentiment(report: dict) -> float:
    """Derive adverse-event sentiment baseline from seriousness indicators."""
    baseline = -0.2
    if report.get("seriousnessdeath") == "1" or report.get("seriousnesshospitalization") == "1":
        baseline = -0.7
    outcomes = report.get("patient", {}).get("reaction", [])
    if any((item.get("reactionoutcome") in {"1", "2"}) for item in outcomes):
        baseline += 0.3
    return float(max(min(baseline, 1.0), -1.0))


@celery_app.task(name="ingestion.openfda", bind=True)
def ingest_openfda(self, drug_name: str, org_id: str, drug_id: str) -> dict:
    """Sync Celery wrapper around async ingestion implementation."""
    return run_async(_ingest_openfda(self, drug_name, org_id, drug_id))


async def _ingest_openfda(self, drug_name: str, org_id: str, drug_id: str) -> dict:
    """Ingest OpenFDA adverse events and map to PatientReview rows idempotently."""
    created = 0
    offset = 0
    page = 0
    task_id = self.request.id
    max_pages = max(1, settings.openfda_max_pages)

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        while True:
            if page >= max_pages:
                logger.info("openfda_page_cap_reached", max_pages=max_pages, drug_name=drug_name)
                break
            params = {
                "search": f'patient.drug.medicinalproduct:"{drug_name}"',
                "limit": 100,
                "skip": offset,
            }
            response = await with_retry(client.get, f"{settings.openfda_base_url}/drug/event.json", params=params)
            if response.status_code == 404:
                break
            response.raise_for_status()
            payload = response.json()
            results = payload.get("results", [])
            if not results:
                break

            async with db_session() as session:
                for report in results:
                    raw_external_id = report.get("safetyreportid")
                    scoped_external_id = f"{drug_id}:openfda:{raw_external_id}" if raw_external_id else None
                    if scoped_external_id:
                        existing = await session.execute(
                            select(PatientReview.id).where(PatientReview.external_id == scoped_external_id)
                        )
                        if existing.scalar_one_or_none():
                            continue

                    reactions = report.get("patient", {}).get("reaction", [])
                    reaction_text = ", ".join(
                        item.get("reactionmeddrapt", "") for item in reactions if item.get("reactionmeddrapt")
                    ) or "adverse event report"
                    review = PatientReview(
                        drug_id=UUID(drug_id),
                        source="openfda",
                        external_id=scoped_external_id,
                        review_text=reaction_text,
                        review_date=_parse_fda_date(report.get("receivedate")),
                        crawled_at=datetime.now(UTC),
                        source_url="https://api.fda.gov/drug/event.json",
                        word_count=len(reaction_text.split()),
                        sentiment_score=_derive_openfda_sentiment(report),
                        overall_sentiment=_derive_openfda_sentiment(report),
                        review_metadata={"org_id": org_id, "raw": report},
                    )
                    session.add(review)
                    created += 1
                await session.commit()

            page += 1
            offset += 100
            await set_job_progress(task_id, min(95, page * 5))
            # OpenFDA allows 240 req/min, so we stay below by sleeping 0.3s/request.
            import asyncio

            await asyncio.sleep(0.3)

    await set_job_progress(task_id, 100)
    return {"status": "ok", "source": "openfda", "created": created}


@celery_app.task(name="ingestion.reddit", bind=True)
def ingest_reddit(self, drug_name: str, org_id: str, drug_id: str) -> dict:
    """Sync Celery wrapper around async ingestion implementation."""
    return run_async(_ingest_reddit(self, drug_name, org_id, drug_id))


async def _ingest_reddit(self, drug_name: str, org_id: str, drug_id: str) -> dict:
    """Ingest Reddit posts/comments mentioning drug and map to SocialMention rows."""

    if not settings.reddit_client_id or not settings.reddit_client_secret:
        logger.warning("reddit_ingestion_missing_credentials_using_public_fallback")
        return await _ingest_reddit_public_fallback(self.request.id, drug_name, org_id, drug_id, reason="missing_credentials")

    created = 0
    scanned = 0
    task_id = self.request.id
    reddit = asyncpraw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        user_agent=settings.reddit_user_agent,
    )

    try:
        async with db_session() as session:
            for idx, sub_name in enumerate(REDDIT_SUBREDDITS, start=1):
                subreddit = await reddit.subreddit(sub_name)
                async for submission in subreddit.search(drug_name, limit=50, sort="new"):
                    scanned += 1
                    text_blob = f"{submission.title}\n{submission.selftext or ''}".strip()
                    if drug_name.lower() not in text_blob.lower():
                        continue

                    submission_external_id = f"{drug_id}:reddit_post:{submission.id}"
                    existing = await session.execute(select(SocialMention.id).where(SocialMention.external_id == submission_external_id))
                    if not existing.scalar_one_or_none():
                        session.add(
                            SocialMention(
                                drug_id=UUID(drug_id),
                                platform="reddit",
                                external_id=submission_external_id,
                                post_id=submission.id,
                                author_handle=str(submission.author) if submission.author else None,
                                source_url=f"https://reddit.com{submission.permalink}",
                                content=text_blob,
                                mention_date=datetime.fromtimestamp(submission.created_utc, tz=UTC),
                                posted_at=datetime.fromtimestamp(submission.created_utc, tz=UTC),
                                engagement_score=float(submission.score),
                                mention_metadata={"org_id": org_id, "engagement_score": float(submission.score)},
                            )
                        )
                        created += 1

                    await submission.comments.replace_more(limit=0)
                    comment_count = 0
                    for comment in submission.comments:
                        if comment_count >= 5:
                            break
                        if drug_name.lower() not in comment.body.lower():
                            continue
                        comment_count += 1

                        comment_external_id = f"{drug_id}:reddit_comment:{comment.id}"
                        comment_existing = await session.execute(select(SocialMention.id).where(SocialMention.external_id == comment_external_id))
                        if comment_existing.scalar_one_or_none():
                            continue

                        session.add(
                            SocialMention(
                                drug_id=UUID(drug_id),
                                platform="reddit",
                                external_id=comment_external_id,
                                post_id=submission.id,
                                author_handle=str(comment.author) if comment.author else None,
                                source_url=f"https://reddit.com{comment.permalink}",
                                content=comment.body,
                                mention_date=datetime.fromtimestamp(comment.created_utc, tz=UTC),
                                posted_at=datetime.fromtimestamp(comment.created_utc, tz=UTC),
                                engagement_score=float(comment.score),
                                mention_metadata={"org_id": org_id, "engagement_score": float(comment.score)},
                            )
                        )
                        created += 1

                await session.commit()
                await set_job_progress(task_id, min(95, idx * 12))
    except asyncprawcore.AsyncPrawcoreException as exc:
        logger.warning("reddit_ingestion_auth_error_using_public_fallback", detail=str(exc))
        return await _ingest_reddit_public_fallback(self.request.id, drug_name, org_id, drug_id, reason="auth_error")
    finally:
        await reddit.close()

    await set_job_progress(task_id, 100)
    return {"status": "ok", "source": "reddit", "created": created, "scanned": scanned}


async def _ingest_reddit_public_fallback(task_id: str, drug_name: str, org_id: str, drug_id: str, reason: str) -> dict:
    """Fallback Reddit ingestion via public JSON search endpoint when OAuth credentials are unavailable."""

    created = 0
    scanned = 0

    headers = {
        "User-Agent": settings.reddit_user_agent,
        "Accept": "application/json",
    }
    params = {
        "q": drug_name,
        "sort": "new",
        "limit": 75,
        "restrict_sr": "false",
        "t": "all",
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(25.0), headers=headers, follow_redirects=True) as client:
        try:
            response = await with_retry(client.get, "https://www.reddit.com/search.json", params=params)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # noqa: BLE001 - fallback should never crash ingestion chord
            logger.warning("reddit_public_fallback_failed", detail=str(exc))
            await set_job_progress(task_id, 100)
            return {
                "status": "skipped",
                "source": "reddit",
                "reason": f"public_fallback_failed:{reason}",
                "created": 0,
                "scanned": 0,
            }

    children = ((payload.get("data") or {}).get("children") or []) if isinstance(payload, dict) else []

    async with db_session() as session:
        for idx, item in enumerate(children, start=1):
            post = item.get("data") if isinstance(item, dict) else None
            if not isinstance(post, dict):
                continue

            scanned += 1
            title = str(post.get("title") or "")
            body = str(post.get("selftext") or "")
            content = f"{title}\n{body}".strip()

            if drug_name.lower() not in content.lower():
                continue

            reddit_id = str(post.get("id") or "")
            permalink = str(post.get("permalink") or "")
            if not reddit_id:
                continue

            external_id = f"{drug_id}:reddit_public_post:{reddit_id}"
            existing = await session.execute(select(SocialMention.id).where(SocialMention.external_id == external_id))
            if existing.scalar_one_or_none():
                continue

            created_utc = post.get("created_utc")
            created_at = datetime.now(UTC)
            if isinstance(created_utc, (int, float)):
                created_at = datetime.fromtimestamp(created_utc, tz=UTC)

            session.add(
                SocialMention(
                    drug_id=UUID(drug_id),
                    platform="reddit",
                    external_id=external_id,
                    post_id=reddit_id,
                    author_handle=str(post.get("author") or "") or None,
                    source_url=f"https://reddit.com{permalink}" if permalink else None,
                    content=content,
                    mention_date=created_at,
                    posted_at=created_at,
                    engagement_score=float(post.get("score") or 0.0),
                    mention_metadata={
                        "org_id": org_id,
                        "fallback": "reddit_public_json",
                        "ingestion_reason": reason,
                    },
                )
            )
            created += 1

            if idx % 20 == 0:
                await session.flush()
                await set_job_progress(task_id, min(95, 10 + idx))

        await session.commit()

    await set_job_progress(task_id, 100)
    return {
        "status": "ok",
        "source": "reddit",
        "mode": "public_fallback",
        "reason": reason,
        "created": created,
        "scanned": scanned,
    }


@celery_app.task(name="ingestion.clinical_trials", bind=True)
def ingest_clinical_trials(self, drug_name: str, drug_id: str) -> dict:
    """Sync Celery wrapper around async ingestion implementation."""
    return run_async(_ingest_clinical_trials(self, drug_name, drug_id))


async def _ingest_clinical_trials(self, drug_name: str, drug_id: str) -> dict:
    """Ingest ClinicalTrials.gov completed studies and upsert by nct_id."""

    created_or_updated = 0
    page_token: str | None = None
    seen_tokens: set[str] = set()
    page_count = 0
    max_pages = max(1, settings.clinical_trials_max_pages)
    task_id = self.request.id

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        while True:
            if page_count >= max_pages:
                logger.info("clinical_trials_page_cap_reached", max_pages=max_pages, drug_name=drug_name)
                break
            params = {
                "query.term": drug_name,
                "filter.overallStatus": "COMPLETED",
                "pageSize": 50,
            }
            if page_token:
                params["pageToken"] = page_token

            response = await with_retry(client.get, "https://clinicaltrials.gov/api/v2/studies", params=params)
            response.raise_for_status()
            payload = response.json()
            studies = payload.get("studies", [])
            if not studies:
                break

            async with db_session() as session:
                for study in studies:
                    protocol = study.get("protocolSection", {})
                    ident = protocol.get("identificationModule", {})
                    status = protocol.get("statusModule", {})
                    outcomes = protocol.get("outcomesModule", {})
                    results = study.get("resultsSection", {}).get("adverseEventsModule", {})

                    nct_id = ident.get("nctId")
                    if not nct_id:
                        continue

                    # Scope unique identifier by drug to prevent cross-drug upsert collisions.
                    scoped_nct_id = f"{drug_id}:{nct_id}"

                    serious_events = results.get("seriousEvents", [])
                    total_affected = 0
                    total_risk = 0
                    for event in serious_events:
                        for stat in event.get("stats", []):
                            total_affected += int(stat.get("numAffected", 0) or 0)
                            total_risk += int(stat.get("numAtRisk", 0) or 0)
                    adverse_event_rate = (total_affected / total_risk) if total_risk else None

                    other_events = results.get("otherEvents", [])
                    discontinuation_proxy = float(len(other_events)) if other_events else None

                    upsert_stmt = insert(ClinicalTrial).values(
                        drug_id=UUID(drug_id),
                        trial_identifier=nct_id,
                        nct_id=scoped_nct_id,
                        title=ident.get("briefTitle", "Untitled trial"),
                        phase=(design_phase := protocol.get("designModule", {}).get("phases", [None])[0]),
                        status=status.get("overallStatus"),
                        summary=protocol.get("descriptionModule", {}).get("briefSummary"),
                        source_url=f"https://clinicaltrials.gov/study/{nct_id}",
                        adverse_event_rate=adverse_event_rate,
                        discontinuation_proxy=discontinuation_proxy,
                        payload={
                            "primaryOutcomes": outcomes.get("primaryOutcomes", []),
                            "adverseEventsModule": results,
                            "phase": design_phase,
                        },
                    )
                    upsert_stmt = upsert_stmt.on_conflict_do_update(
                        index_elements=[ClinicalTrial.nct_id],
                        set_={
                            "title": upsert_stmt.excluded.title,
                            "phase": upsert_stmt.excluded.phase,
                            "status": upsert_stmt.excluded.status,
                            "summary": upsert_stmt.excluded.summary,
                            "source_url": upsert_stmt.excluded.source_url,
                            "adverse_event_rate": upsert_stmt.excluded.adverse_event_rate,
                            "discontinuation_proxy": upsert_stmt.excluded.discontinuation_proxy,
                            "payload": upsert_stmt.excluded.payload,
                        },
                    )
                    await session.execute(upsert_stmt)
                    created_or_updated += 1

                await session.commit()

            page_count += 1
            page_token = payload.get("nextPageToken")
            if not page_token:
                break
            if page_token in seen_tokens:
                logger.warning("clinical_trials_page_token_cycle", token=page_token, drug_name=drug_name)
                break
            seen_tokens.add(page_token)

    await set_job_progress(task_id, 100)
    return {"status": "ok", "source": "clinical_trials", "upserts": created_or_updated}


@celery_app.task(name="analysis.trigger_full", bind=True)
def trigger_full_analysis(self, drug_id: str, org_id: str, drug_name: str) -> dict:
    """Orchestrate ingestion tasks in parallel and trigger gap analysis callback."""
    from apps.worker.tasks.analysis import run_gap_analysis

    header = [
        ingest_openfda.s(drug_name, org_id, drug_id),
        ingest_reddit.s(drug_name, org_id, drug_id),
        ingest_clinical_trials.s(drug_name, drug_id),
    ]
    workflow = chord(header)(run_gap_analysis.s(drug_id=drug_id, org_id=org_id))

    header_ids: list[str] = []
    if workflow.parent and getattr(workflow.parent, "results", None):
        header_ids = [result.id for result in workflow.parent.results]

    return {
        "status": "started",
        "root_task_id": self.request.id,
        "chord_id": workflow.id,
        "tasks": {
            "openfda": header_ids[0] if len(header_ids) > 0 else None,
            "reddit": header_ids[1] if len(header_ids) > 1 else None,
            "clinical_trials": header_ids[2] if len(header_ids) > 2 else None,
            "callback": workflow.id,
        },
    }
