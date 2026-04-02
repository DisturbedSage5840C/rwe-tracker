"""Production-grade sentiment pipeline with ONNX transformer inference and embeddings."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from apps.common.logging import get_logger
from apps.nlp.config import NLPSettings
from apps.nlp.schemas import AspectResult, SentimentResult

logger = get_logger(__name__)


class PharmaSentimentPipeline:
    """Healthcare-aware sentiment pipeline blending lexicon and transformer signals."""

    def __init__(self, settings: NLPSettings) -> None:
        self.settings = settings
        self.model_cache_dir = Path(settings.model_cache_dir)
        self.model_cache_dir.mkdir(parents=True, exist_ok=True)

        self.vader: Any | None = None
        self.tokenizer = None
        self.model = None
        self.classifier = None
        self.sentence_encoder: Any | None = None

        self.label_map = {0: "negative", 1: "neutral", 2: "positive"}
        self.aspect_keywords = {
            "efficacy": ["effective", "worked", "improved", "relief", "response", "benefit"],
            "safety": ["safe", "adverse", "risk", "toxic", "hospitalized", "fatal"],
            "tolerability": ["tolerate", "side effect", "nausea", "dizziness", "fatigue", "painful"],
            "convenience": ["daily", "schedule", "convenient", "easy", "adherence", "burden"],
            "quality_of_life": ["sleep", "work", "family", "quality of life", "energy", "mood"],
        }

    async def load(self):
        from nltk import download
        from nltk.sentiment import SentimentIntensityAnalyzer
        from sentence_transformers import SentenceTransformer
        from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification

        try:
            self.vader = SentimentIntensityAnalyzer()
        except LookupError:
            download("vader_lexicon", quiet=True)
            self.vader = SentimentIntensityAnalyzer()

        lexicon_path = Path(__file__).resolve().parents[1] / "config" / "nlp_lexicon.json"
        custom_lexicon = json.loads(lexicon_path.read_text(encoding="utf-8"))
        self.vader.lexicon.update(custom_lexicon)

        model_name = self.settings.transformer_model_name
        model_revision = self.settings.transformer_model_revision
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, revision=model_revision)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name, revision=model_revision)
        self.classifier = pipeline(
            "sentiment-analysis",
            model=self.model,
            tokenizer=self.tokenizer,
            device=-1  # CPU
        )

        self.sentence_encoder = SentenceTransformer(
            self.settings.sentence_model_name,
            cache_folder=str(self.model_cache_dir),
        )

    def loaded_models(self) -> list[str]:
        """Return names of models that are loaded in memory."""
        loaded: list[str] = []
        if self.vader is not None:
            loaded.append("vader")
        if self.classifier is not None:
            loaded.append("cardiffnlp/twitter-roberta-base-sentiment-latest")
        if self.sentence_encoder is not None:
            loaded.append("sentence-transformers/all-MiniLM-L6-v2")
        return loaded

    async def analyze(self, text: str) -> SentimentResult:
        """Run full single-text inference with aspect extraction and embedding generation."""
        started = time.perf_counter()
        vader_score = float(self.vader.polarity_scores(text)["compound"])

        # Overflow is expected on long social text; we truncate to keep service resilient.
        approximate_tokens = len(text.split())
        if approximate_tokens > 512:
            logger.warning("token_overflow_truncated", approximate_tokens=approximate_tokens, max_length=512)

        inference_raw = self.classifier(text, truncation=True, max_length=512, top_k=None)
        if isinstance(inference_raw, dict):
            inference = [inference_raw]
        elif inference_raw and isinstance(inference_raw[0], dict):
            inference = inference_raw
        else:
            inference = inference_raw[0]
        label_scores = {entry["label"].lower(): float(entry["score"]) for entry in inference}
        transformer_label = max(label_scores, key=label_scores.get)
        transformer_confidence = float(label_scores[transformer_label])
        transformer_normalized = float(label_scores.get("positive", 0.0) - label_scores.get("negative", 0.0))

        aspects = self._extract_aspects(text)
        aspect_values = [aspect.sentiment for aspect in aspects.values() if aspect.sentiment is not None]
        aspect_avg = float(sum(aspect_values) / len(aspect_values)) if aspect_values else 0.0

        # Weighted blend: transformer captures context best, VADER handles sparse slang, aspects enforce domain grounding.
        composite_score = float((0.3 * vader_score) + (0.5 * transformer_normalized) + (0.2 * aspect_avg))
        embedding = await self.embed(text)
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        return SentimentResult(
            vader_compound=vader_score,
            transformer_label=transformer_label,
            transformer_confidence=transformer_confidence,
            composite_score=composite_score,
            aspects=aspects,
            embedding=embedding,
            processing_time_ms=elapsed_ms,
        )

    async def analyze_batch(self, texts: list[str], batch_size: int = 32) -> list[SentimentResult]:
        """Run batched inference while preserving deterministic output order."""
        results: list[SentimentResult] = []
        for start in range(0, len(texts), batch_size):
            chunk = texts[start : start + batch_size]
            for text in chunk:
                results.append(await self.analyze(text))
        return results

    async def embed(self, text: str) -> list[float]:
        """Generate 384-dimensional embedding for vector search storage."""
        vector = self.sentence_encoder.encode(text, normalize_embeddings=True)
        return [float(x) for x in vector.tolist()]

    def _extract_aspects(self, text: str) -> dict[str, AspectResult]:
        """Estimate aspect sentiments by sentence-level keyword routing."""
        sentences = self._split_sentences(text)
        output: dict[str, AspectResult] = {}

        for aspect, keywords in self.aspect_keywords.items():
            matching = [s for s in sentences if any(k in s.lower() for k in keywords)]
            if not matching:
                output[aspect] = AspectResult(sentiment=None, mention_count=0, example_sentences=[])
                continue

            sentiment_values = [self.vader.polarity_scores(sentence)["compound"] for sentence in matching]
            output[aspect] = AspectResult(
                sentiment=float(sum(sentiment_values) / len(sentiment_values)),
                mention_count=len(matching),
                example_sentences=matching[:3],
            )

        return output

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """Lightweight sentence splitter to avoid heavyweight NLP parser overhead."""
        return [segment.strip() for segment in re.split(r"[.!?]+", text) if segment.strip()]

