"""Application error types and RFC 7807 problem details helpers."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base class for predictable domain and infrastructure errors."""

    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    title: str = "Application Error"

    def __init__(self, detail: str, type_uri: str = "about:blank", extra: dict[str, Any] | None = None):
        super().__init__(detail)
        self.detail = detail
        self.type_uri = type_uri
        self.extra = extra or {}


class ValidationAppError(AppError):
    """Raised when domain validation fails beyond schema validation."""

    status_code = HTTPStatus.BAD_REQUEST
    title = "Validation Error"


class NotFoundError(AppError):
    """Raised when requested resources are missing."""

    status_code = HTTPStatus.NOT_FOUND
    title = "Not Found"


class AuthError(AppError):
    """Raised when authentication or authorization checks fail."""

    status_code = HTTPStatus.UNAUTHORIZED
    title = "Authentication Error"


class ForbiddenError(AppError):
    """Raised when caller is authenticated but lacks authorization."""

    status_code = HTTPStatus.FORBIDDEN
    title = "Forbidden"


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Convert known domain errors into consistent envelope payloads."""
    body = {
        "data": None,
        "meta": {
            "request_id": getattr(request.state, "request_id", None),
        },
        "errors": [
            {
                "code": exc.title,
                "message": exc.detail,
                "type": exc.type_uri,
                "status": exc.status_code,
                "instance": str(request.url),
            }
        ],
    }
    if exc.extra:
        body["meta"].update(exc.extra)
    return JSONResponse(status_code=exc.status_code, content=body)
