"""Model loader abstraction for NLP pipelines."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LoadedModel:
    """Minimal placeholder for production model artifacts."""

    name: str


def load_default_model() -> LoadedModel:
    """Load and return the baseline NLP model artifact."""
    return LoadedModel(name="baseline-perception-model")
