"""NLP sentiment pipeline behavior tests with deterministic stubs."""

from __future__ import annotations

import numpy as np
import pytest

from apps.nlp.config import NLPSettings
from apps.nlp.pipelines.sentiment import PharmaSentimentPipeline


class _FakeTensor:
    def __init__(self, values: np.ndarray) -> None:
        self._values = values

    def detach(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return self._values


class _FakeModelOutput:
    def __init__(self, logits: np.ndarray) -> None:
        self.logits = _FakeTensor(logits)


class _FakeTokenizer:
    def __call__(self, text: str, truncation: bool, max_length: int, return_tensors: str):
        del text, truncation, max_length, return_tensors
        return {"input_ids": [1, 2, 3]}


class _FakeOrtModel:
    def __call__(self, **_tokens):
        return _FakeModelOutput(np.array([[-0.5, 0.2, 1.2]], dtype=float))


class _FakeSentenceEncoder:
    def encode(self, _text: str, normalize_embeddings: bool = True):
        del normalize_embeddings
        return np.zeros((384,), dtype=float)


class _FakeVader:
    def polarity_scores(self, text: str):
        lowered = text.lower()
        if "severe nausea" in lowered or "had to stop" in lowered:
            return {"compound": -0.7}
        if "life-changing" in lowered or "completely gone" in lowered:
            return {"compound": 0.9}
        if "works well" in lowered or "worked" in lowered:
            return {"compound": 0.6}
        return {"compound": 0.1}


@pytest.fixture
def pipeline() -> PharmaSentimentPipeline:
    settings = NLPSettings()
    sentiment_pipeline = PharmaSentimentPipeline(settings)
    sentiment_pipeline.vader = _FakeVader()
    sentiment_pipeline.tokenizer = _FakeTokenizer()
    sentiment_pipeline.transformer_ort = _FakeOrtModel()
    sentiment_pipeline.sentence_encoder = _FakeSentenceEncoder()
    return sentiment_pipeline


@pytest.mark.asyncio
async def test_pharma_negative_review(pipeline: PharmaSentimentPipeline) -> None:
    result = await pipeline.analyze("This drug gave me severe nausea and I had to stop")
    assert result.composite_score < 0


@pytest.mark.asyncio
async def test_pharma_positive_review(pipeline: PharmaSentimentPipeline) -> None:
    result = await pipeline.analyze("Life-changing medication, my symptoms are completely gone")
    assert result.composite_score > 0.5


@pytest.mark.asyncio
async def test_aspect_efficacy_detected(pipeline: PharmaSentimentPipeline) -> None:
    result = await pipeline.analyze("This treatment works well and gives clear relief")
    assert result.aspects["efficacy"].mention_count > 0


@pytest.mark.asyncio
async def test_batch_consistency(pipeline: PharmaSentimentPipeline) -> None:
    text = "This treatment works well for me"
    single = await pipeline.analyze(text)
    batch = await pipeline.analyze_batch([text], batch_size=1)
    assert len(batch) == 1
    assert batch[0].composite_score == single.composite_score


@pytest.mark.asyncio
async def test_long_text_truncation(pipeline: PharmaSentimentPipeline) -> None:
    long_text = "word " * 2000
    result = await pipeline.analyze(long_text)
    assert result.composite_score is not None


@pytest.mark.asyncio
async def test_embedding_dimensions(pipeline: PharmaSentimentPipeline) -> None:
    vector = await pipeline.embed("test")
    assert len(vector) == 384
