"""Read-only SQL for the settings pages: one setting's current version, its
history and the notification outbox. Nothing here writes, and no secret value
or blob is ever selected (the statements themselves return NULL for them)."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from backend.admin.repositories.views import parse_json


async def entry_version(conn: AsyncConnection, key: str) -> Optional[tuple[int, bool, Any]]:
    """``(version, cleared, value)`` of one setting, or None when never written.
    The value is NULL for a secret or a cleared row."""
    row = (
        await conn.execute(
            text(
                "SELECT version, cleared, CASE WHEN is_secret OR cleared THEN NULL "
                "ELSE value::text END AS value FROM settings.entries WHERE key = :k"
            ),
            {"k": key},
        )
    ).first()
    if row is None:
        return None
    return row.version, row.cleared, parse_json(row.value) if row.value is not None else None


async def history_for_display(conn: AsyncConnection, key: str, limit: int) -> list[Any]:
    """Versions of one setting, newest first. A secret's value and blob are
    never selected: only whether a sealed version is still held."""
    return (
        await conn.execute(
            text(
                "SELECT version, action, source, actor, at, is_secret, cleared, "
                "(blob IS NOT NULL) AS has_blob, "
                "CASE WHEN is_secret OR cleared THEN NULL ELSE value::text END AS value "
                "FROM settings.history WHERE key = :k ORDER BY version DESC LIMIT :n"
            ),
            {"k": key, "n": limit},
        )
    ).all()


async def recent_notifications(conn: AsyncConnection, limit: int) -> list[Any]:
    return (
        await conn.execute(
            text(
                "SELECT kind, status, attempts, created_at, sent_at, "
                "payload->>'setting' AS setting, payload->>'tier' AS tier, "
                "payload->>'action' AS action, payload->>'version' AS version "
                "FROM admin.notifications ORDER BY created_at DESC, id LIMIT :n"
            ),
            {"n": limit},
        )
    ).all()
