"""Reusable cursor pagination utilities for repository query methods."""

from __future__ import annotations

from typing import Any, TypeVar

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.schemas.pagination import CursorPage, CursorToken, decode_cursor, encode_cursor

T = TypeVar("T")


async def paginate_by_created_desc(
    session: AsyncSession,
    model: type[T],
    base_filters: list[Any],
    cursor: str | None,
    limit: int,
) -> CursorPage[T]:
    """Paginate records by created_at DESC and id DESC using opaque cursor tokens."""
    statement = select(model).where(*base_filters)

    if cursor:
        token = decode_cursor(cursor)
        statement = statement.where(
            or_(
                model.created_at < token.created_at,
                and_(model.created_at == token.created_at, model.id < token.id),
            )
        )

    statement = statement.order_by(model.created_at.desc(), model.id.desc()).limit(limit + 1)
    result = await session.execute(statement)
    rows = list(result.scalars().all())

    has_more = len(rows) > limit
    items = rows[:limit]

    next_cursor = None
    if has_more and items:
        final = items[-1]
        next_cursor = encode_cursor(CursorToken(created_at=final.created_at, id=final.id))

    prev_cursor = None
    if cursor and items:
        prev_cursor = cursor

    return CursorPage(items=items, next_cursor=next_cursor, prev_cursor=prev_cursor)
