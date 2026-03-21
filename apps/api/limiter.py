"""Rate limiting primitives shared by API routers and application setup."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from apps.api.config import get_settings

settings = get_settings()
limiter = Limiter(key_func=get_remote_address)
AUTH_LIMIT = settings.authenticated_rate_limit
UNAUTH_LIMIT = settings.unauthenticated_rate_limit
