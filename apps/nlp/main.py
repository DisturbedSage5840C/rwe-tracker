"""FastAPI entrypoint for NLP inference microservice."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi import HTTPException

from apps.common.logging import configure_logging, get_logger
from apps.nlp.config import get_nlp_settings
from apps.nlp.pipelines.gap_analysis import GapAnalysisPipeline
from apps.nlp.pipelines.sentiment import PharmaSentimentPipeline
from apps.nlp.schemas import AnalyzeBatchRequest, AnalyzeRequest, EmbedRequest, GapAnalysisRequest, GapReport, SentimentResult

configure_logging()
logger = get_logger(__name__)
settings = get_nlp_settings()

sentiment_pipeline = PharmaSentimentPipeline(settings=settings)
gap_pipeline = GapAnalysisPipeline()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load heavy model artifacts exactly once per service process."""
    await sentiment_pipeline.load()
    logger.info("nlp_models_loaded", models=sentiment_pipeline.loaded_models())
    yield


app = FastAPI(title="RWE NLP Service", lifespan=lifespan)


@app.get("/health")
async def healthcheck() -> dict:
    """Service health endpoint exposing model load state and version info."""
    return {
        "status": "ok",
        "models_loaded": sentiment_pipeline.loaded_models(),
        "model_version": settings.model_version,
    }


@app.post("/analyze", response_model=SentimentResult)
async def analyze(payload: AnalyzeRequest) -> SentimentResult:
    """Run single-text NLP sentiment and embedding inference."""
    return await sentiment_pipeline.analyze(payload.text)


@app.post("/analyze/batch", response_model=list[SentimentResult])
async def analyze_batch(payload: AnalyzeBatchRequest) -> list[SentimentResult]:
    """Run batched NLP analysis with configurable request-level chunk sizing."""
    if len(payload.texts) > settings.nlp_max_batch_size:
        raise HTTPException(status_code=400, detail="Batch size exceeds configured maximum")
    batch_size = payload.batch_size or settings.nlp_batch_size
    return await sentiment_pipeline.analyze_batch(payload.texts, batch_size=batch_size)


@app.post("/embed", response_model=list[float])
async def embed(payload: EmbedRequest) -> list[float]:
    """Generate a single embedding vector for semantic search."""
    return await sentiment_pipeline.embed(payload.text)


@app.post("/gap-analysis", response_model=GapReport)
async def gap_analysis(payload: GapAnalysisRequest) -> GapReport:
    """Run statistical gap analysis for a drug using aggregate inputs."""
    return await gap_pipeline.analyze_drug(
        drug_id=payload.drug_id,
        clinical_data=payload.clinical_data,
        patient_reviews=payload.patient_reviews,
        social_mentions=payload.social_mentions,
    )
