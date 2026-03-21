"""Asynchronous NLP pipeline for claim-vs-experience text analysis."""

from __future__ import annotations

from apps.nlp.models.loader import load_default_model


async def analyze_perception_gap(claim_text: str, patient_text: str) -> dict[str, float]:
    """Compute lightweight placeholder NLP metrics for scaffold purposes."""
    _ = load_default_model()

    # Heuristic placeholder for scaffold; replace with proper model inference later.
    shared_terms = len(set(claim_text.lower().split()) & set(patient_text.lower().split()))
    alignment_score = min(shared_terms / 10.0, 1.0)

    positive_cues = ["better", "effective", "improved", "relief"]
    sentiment_hits = sum(1 for cue in positive_cues if cue in patient_text.lower())
    sentiment_score = min(sentiment_hits / len(positive_cues), 1.0)

    return {"alignment_score": alignment_score, "sentiment_score": sentiment_score}
