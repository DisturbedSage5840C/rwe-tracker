"""Security helper functions for password, token, and API key hashing."""

from __future__ import annotations

import hashlib
import secrets

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify plaintext password against bcrypt hash."""
    return pwd_context.verify(password, hashed_password)


def generate_refresh_token() -> str:
    """Generate opaque refresh token value."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """Hash refresh token with SHA-256 for DB storage and lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    """Generate API key string only shown once to caller."""
    return f"rwe_{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    """Hash API key value for secure DB storage and verification."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()
