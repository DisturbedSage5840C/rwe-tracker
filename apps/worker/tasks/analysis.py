"""Celery analysis bridge that enriches data via NLP service and persists reports."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy import select

from apps.api.config import get_settings
from apps.api.models.clinical_trial import ClinicalTrial
from apps.api.models.patient_review import PatientReview
from apps.api.models.perception_report import PerceptionReport
from apps.api.models.social_mention import SocialMention
from apps.common.logging import get_logger
from apps.worker.celery_app import celery_app
from apps.worker.tasks.utils import db_session, set_job_progress, set_job_result, with_retry

logger = get_logger(__name__)
settings = get_settings()


@celery_app.task(name="analysis.run_gap_analysis", bind=True)
async def run_gap_analysis(self, _ingestion_results: list[dict], drug_id: str, org_id: str) -> dict:
    """Enrich raw text with NLP predictions and persist final gap report."""
    task_id = self.request.id
    await set_job_progress(task_id, 5)

    async with db_session() as session:
        pending_reviews = list(
            (
                await session.execute(
                    select(PatientReview)
                    .where(PatientReview.drug_id == UUID(drug_id), PatientReview.sentiment_score.is_(None))
                    .order_by(PatientReview.created_at.asc())
                )
            )
            .scalars()
            .all()
        )

        pending_social = list(
            (
                await session.execute(
                    select(SocialMention)
                    .where(SocialMention.drug_id == UUID(drug_id), SocialMention.sentiment_score.is_(None))
                    .order_by(SocialMention.created_at.asc())
                )
            )
            .scalars()
            .all()
        )

    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        chunk_size = settings.nlp_batch_size
        review_texts = [item.review_text for item in pending_reviews]
        social_texts = [item.content for item in pending_social]

        enriched_reviews: list[dict] = []
        for start in range(0, len(review_texts), 100):
            chunk = review_texts[start : start + 100]
            if not chunk:
                continue
            response = await with_retry(
                client.post,
                f"{settings.nlp_service_url}/analyze/batch",
                json={"texts": chunk, "batch_size": min(chunk_size, 100)},
            )
            response.raise_for_status()
            enriched_reviews.extend(response.json())
            await set_job_progress(task_id, min(55, 10 + int((start + len(chunk)) / max(len(review_texts), 1) * 45)))

        enriched_social: list[dict] = []
        for start in range(0, len(social_texts), 100):
            chunk = social_texts[start : start + 100]
            if not chunk:
                continue
            response = await with_retry(
                client.post,
                f"{settings.nlp_service_url}/analyze/batch",
                json={"texts": chunk, "batch_size": min(chunk_size, 100)},
            )
            response.raise_for_status()
            enriched_social.extend(response.json())
            await set_job_progress(task_id, min(75, 55 + int((start + len(chunk)) / max(len(social_texts), 1) * 20)))

    async with db_session() as session:
        for row, result in zip(pending_reviews, enriched_reviews, strict=False):
            aspects = result.get("aspects", {})
            row.sentiment_score = result.get("composite_score")
            row.overall_sentiment = result.get("composite_score")
            row.efficacy_sentiment = (aspects.get("efficacy") or {}).get("sentiment")
            row.safety_sentiment = (aspects.get("safety") or {}).get("sentiment")
            row.tolerability_sentiment = (aspects.get("tolerability") or {}).get("sentiment")
            row.convenience_sentiment = (aspects.get("convenience") or {}).get("sentiment")
            row.qol_sentiment = (aspects.get("quality_of_life") or {}).get("sentiment")
            row.embedding = result.get("embedding")

        for row, result in zip(pending_social, enriched_social, strict=False):
            row.sentiment_score = result.get("composite_score")
            row.overall_sentiment = result.get("composite_score")
            row.embedding = result.get("embedding")

        await session.commit()

        trials = list((await session.execute(select(ClinicalTrial).where(ClinicalTrial.drug_id == UUID(drug_id)))).scalars().all())
        reviews = list((await session.execute(select(PatientReview).where(PatientReview.drug_id == UUID(drug_id)))).scalars().all())
        social = list((await session.execute(select(SocialMention).where(SocialMention.drug_id == UUID(drug_id)))).scalars().all())

        clinical_data = {
            "efficacy": float(sum([1.0 - (t.adverse_event_rate or 0.0) for t in trials]) / max(len(trials), 1)),
            "safety": float(sum([1.0 - (t.adverse_event_rate or 0.0) for t in trials]) / max(len(trials), 1)),
            "tolerability": float(sum([1.0 - ((t.discontinuation_proxy or 0.0) / 100.0) for t in trials]) / max(len(trials), 1)),
            "convenience": 0.6,
            "quality_of_life": 0.6,
            "adherence": 0.6,
            "trust": 0.6,
        }

        review_payload = [
            {
                "efficacy": row.efficacy_sentiment,
                "safety": row.safety_sentiment,
                "tolerability": row.tolerability_sentiment,
                "convenience": row.convenience_sentiment,
                "quality_of_life": row.qol_sentiment,
                "adherence": row.overall_sentiment,
                "trust": row.overall_sentiment,
            }
            for row in reviews
        ]
        social_payload = [
            {
                "efficacy": row.overall_sentiment,
                "safety": row.overall_sentiment,
                "tolerability": row.overall_sentiment,
                "convenience": row.overall_sentiment,
                "quality_of_life": row.overall_sentiment,
                "adherence": row.overall_sentiment,
                "trust": row.overall_sentiment,
            }
            for row in social
        ]

    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        gap_response = await with_retry(
            client.post,
            f"{settings.nlp_service_url}/gap-analysis",
            json={
                "drug_id": drug_id,
                "clinical_data": clinical_data,
                "patient_reviews": review_payload,
                "social_mentions": social_payload,
            },
        )
        gap_response.raise_for_status()
        gap_report = gap_response.json()

    async with db_session() as session:
        dimensions = gap_report.get("dimensions", [])
        dominant_gap = max(dimensions, key=lambda item: abs(item.get("gap_magnitude", 0.0)), default=None)
        payload = {
            "dimensions": dimensions,
            "insights": gap_report.get("insights", []),
            "org_id": org_id,
            "generated_at": datetime.now(UTC).isoformat(),
        }
        report = PerceptionReport(
            drug_id=UUID(drug_id),
            summary="Automated gap analysis generated by NLP service",
            perception_score=float(1.0 - gap_report.get("overall_score", 0.0)),
            trial_score=float(sum(clinical_data.values()) / max(len(clinical_data), 1)),
            gap_score=float(abs(dominant_gap.get("gap_magnitude", 0.0)) if dominant_gap else 0.0),
            confidence_interval_lower=float(dominant_gap.get("ci_lower", 0.0) if dominant_gap else 0.0),
            confidence_interval_upper=float(dominant_gap.get("ci_upper", 0.0) if dominant_gap else 0.0),
            sample_size_reviews=len(reviews),
            sample_size_social=len(social),
            methodology_version="phase3-gap-v1",
            payload=payload,
        )
        session.add(report)
        await session.commit()
        await session.refresh(report)

    result = {"status": "ok", "report_id": str(report.id), "drug_id": drug_id}
    await set_job_progress(task_id, 100)
    await set_job_result(task_id, result, ttl_seconds=86400)
    logger.info("gap_analysis_complete", drug_id=drug_id, report_id=str(report.id))
    return result
