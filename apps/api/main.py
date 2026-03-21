"""Application entrypoint for the RWE Perception Tracker API service."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from apps.api.config import get_settings
from apps.api.limiter import limiter
from apps.api.middleware.request_id import RequestIDMiddleware
from apps.api.routers import analysis, auth, drugs, health
from apps.common.errors import AppError, app_error_handler
from apps.common.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Log startup and shutdown lifecycle events for observability."""
    logger.info("api_starting", app_name=settings.app_name, environment=settings.environment)
    yield
    logger.info("api_stopping", app_name=settings.app_name)


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_exception_handler(AppError, app_error_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-ID"],
)
app.add_middleware(RequestIDMiddleware)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, _: RateLimitExceeded) -> JSONResponse:
    """Return rate-limit errors in common envelope shape."""
    return JSONResponse(
        status_code=429,
        content={
            "data": None,
            "meta": {"request_id": getattr(request.state, "request_id", None)},
            "errors": [{"code": "rate_limit", "message": "Rate limit exceeded"}],
        },
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request, exc: RequestValidationError) -> JSONResponse:
    """Return request validation problems in common envelope format."""
    return JSONResponse(
        status_code=400,
        content={
            "data": None,
            "meta": {"request_id": getattr(request.state, "request_id", None)},
            "errors": [{"code": "validation_error", "message": "Request validation failed", "details": exc.errors()}],
        },
    )


app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(drugs.router, prefix="/drugs", tags=["drugs"])
app.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
