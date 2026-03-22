"""Centralized environment-backed settings for the API service."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="RWE Perception Tracker API", alias="APP_NAME")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    api_port: int = Field(default=8000, alias="API_PORT")

    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")
    secret_key: str = Field(min_length=32, alias="SECRET_KEY")
    jwt_algorithm: Literal["HS256"] = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_issuer: str = Field(default="rwe-tracker-api", alias="JWT_ISSUER")
    jwt_audience: str = Field(default="rwe-tracker-clients", alias="JWT_AUDIENCE")
    access_token_expire_minutes: int = Field(default=15, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=30, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    authenticated_rate_limit: str = Field(default="100/minute", alias="AUTHENTICATED_RATE_LIMIT")
    unauthenticated_rate_limit: str = Field(default="10/minute", alias="UNAUTHENTICATED_RATE_LIMIT")
    cors_allowed_origins: list[str] = Field(default=["http://localhost:3000"], alias="CORS_ALLOWED_ORIGINS")

    nlp_service_url: str = Field(alias="NLP_SERVICE_URL")
    nlp_batch_size: int = Field(default=100, alias="NLP_BATCH_SIZE")
    nlp_max_batch_size: int = Field(default=500, alias="NLP_MAX_BATCH_SIZE")
    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    openfda_base_url: str = Field(alias="OPENFDA_BASE_URL")
    openfda_max_pages: int = Field(default=8, alias="OPENFDA_MAX_PAGES")
    clinical_trials_max_pages: int = Field(default=12, alias="CLINICAL_TRIALS_MAX_PAGES")

    reddit_client_id: str = Field(default="", alias="REDDIT_CLIENT_ID")
    reddit_client_secret: str = Field(default="", alias="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = Field(default="rwe-tracker-bot/1.0", alias="REDDIT_USER_AGENT")


@lru_cache
def get_settings() -> Settings:
    """Cache settings to avoid repeated env parsing and validation."""
    return Settings()
