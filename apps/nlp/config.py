"""Environment-backed settings for NLP microservice runtime behavior."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class NLPSettings(BaseSettings):
    """NLP service settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    nlp_batch_size: int = Field(default=32, alias="NLP_BATCH_SIZE")
    nlp_max_batch_size: int = Field(default=500, alias="NLP_MAX_BATCH_SIZE")
    model_cache_dir: str = Field(
        default_factory=lambda: str(Path.home() / ".cache" / "rwe_nlp_models"),
        alias="NLP_MODEL_CACHE_DIR",
    )
    transformer_model_name: str = Field(
        default="cardiffnlp/twitter-roberta-base-sentiment-latest",
        alias="NLP_TRANSFORMER_MODEL",
    )
    transformer_model_revision: str = Field(default="main", alias="NLP_TRANSFORMER_REVISION")
    sentence_model_name: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        alias="NLP_SENTENCE_MODEL",
    )
    model_version: str = Field(default="phase3-v1", alias="NLP_MODEL_VERSION")


@lru_cache
def get_nlp_settings() -> NLPSettings:
    """Return cached NLP settings instance."""
    return NLPSettings()
