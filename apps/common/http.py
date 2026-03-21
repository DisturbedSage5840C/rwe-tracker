"""Shared async HTTP client helpers for inter-service communication."""

from __future__ import annotations

import httpx


def build_async_client(timeout_seconds: float = 20.0) -> httpx.AsyncClient:
    """Create an AsyncClient with sane defaults used across services."""
    return httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds))
