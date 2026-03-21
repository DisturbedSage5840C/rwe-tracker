"""Worker tests validating Celery task registration."""

from __future__ import annotations

from apps.worker.celery_app import celery_app


def test_phase3_tasks_registered() -> None:
    """Celery app should include the ingestion and analysis phase 3 task set."""
    celery_app.loader.import_default_modules()
    assert "ingestion.openfda" in celery_app.tasks
    assert "ingestion.reddit" in celery_app.tasks
    assert "ingestion.clinical_trials" in celery_app.tasks
    assert "analysis.trigger_full" in celery_app.tasks
    assert "analysis.run_gap_analysis" in celery_app.tasks
