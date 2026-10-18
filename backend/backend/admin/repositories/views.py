"""Read-only SQL for the portal's pages. Nothing here writes.

The configuration query never selects a secret's value or blob: for a secret
row the ``value`` column is replaced by NULL in the statement itself, so a
secret cannot reach the process, let alone a page.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncConnection

from backend.admin.repositories.tables import audit_log, sessions


async def ping(conn: AsyncConnection) -> bool:
    return (await conn.execute(text("SELECT 1"))).scalar_one() == 1


async def service_states(conn: AsyncConnection) -> list[Any]:
    """One row per reporting service instance: names and numbers only."""
    return (
        await conn.execute(
            text(
                "SELECT service, instance, revision_applied, restart_pending, "
                "cardinality(rejected_keys) AS rejected, env_overrides, "
                "extract(epoch FROM (now() - reported_at))::bigint AS age_seconds "
                "FROM settings.service_state ORDER BY service, instance LIMIT 500"
            )
        )
    ).all()


async def manifest_revision(conn: AsyncConnection) -> Optional[int]:
    return (
        await conn.execute(text("SELECT revision FROM settings.manifest WHERE id = 1"))
    ).scalar_one_or_none()


async def entries_for_display(conn: AsyncConnection) -> list[Any]:
    """Settings rows without any secret material (see the module docstring)."""
    return (
        await conn.execute(
            text(
                "SELECT key, is_secret, cleared, version, source, updated_by, updated_at, "
                "CASE WHEN is_secret OR cleared THEN NULL ELSE value::text END AS value "
                "FROM settings.entries ORDER BY key"
            )
        )
    ).all()


def parse_json(raw: Any) -> Any:
    if isinstance(raw, (str, bytes)):
        return json.loads(raw)
    return raw


async def platform_counts(conn: AsyncConnection) -> dict:
    """The counts of ``admin.platform_counts()`` (see postgres/ensure-admin-roles.sh)."""
    return parse_json((await conn.execute(text("SELECT admin.platform_counts()"))).scalar_one())


_AUDIT_COLUMNS = (
    audit_log.c.seq, audit_log.c.id, audit_log.c.at, audit_log.c.actor_kind,
    audit_log.c.actor_email, audit_log.c.ip, audit_log.c.action,
    audit_log.c.target_type, audit_log.c.target_id, audit_log.c.outcome,
    audit_log.c.before, audit_log.c.after, audit_log.c.detail, audit_log.c.request_id,
)


async def audit_page(
    conn: AsyncConnection,
    *,
    before_seq: Optional[int],
    actor: Optional[str],
    action: Optional[str],
    outcome: Optional[str],
    since: Optional[datetime],
    until: Optional[datetime],
    limit: int,
) -> list[Any]:
    """Newest first, ``seq < before_seq`` (keyset); ``limit + 1`` rows so the
    caller can tell whether another page exists."""
    where = []
    if before_seq is not None:
        where.append(audit_log.c.seq < before_seq)
    if actor:
        where.append(audit_log.c.actor_email == actor)
    if action:
        where.append(
            or_(
                audit_log.c.action == action,
                func.starts_with(audit_log.c.action, action + "."),
            )
        )
    if outcome:
        where.append(audit_log.c.outcome == outcome)
    if since is not None:
        where.append(audit_log.c.at >= since)
    if until is not None:
        where.append(audit_log.c.at < until)
    query = (
        select(*_AUDIT_COLUMNS)
        .where(and_(*where) if where else text("true"))
        .order_by(audit_log.c.seq.desc())
        .limit(limit + 1)
    )
    return (await conn.execute(query)).all()


async def audit_head(conn: AsyncConnection) -> Optional[tuple[int, bytes, datetime]]:
    row = (
        await conn.execute(
            select(audit_log.c.seq, audit_log.c.row_hash, audit_log.c.at)
            .order_by(audit_log.c.seq.desc())
            .limit(1)
        )
    ).first()
    return (row[0], bytes(row[1]), row[2]) if row else None


async def live_session_count(conn: AsyncConnection, email: str, now: datetime) -> int:
    return (
        await conn.execute(
            select(func.count())
            .select_from(sessions)
            .where(
                sessions.c.email == email,
                sessions.c.revoked_at.is_(None),
                sessions.c.idle_expires_at > now,
                sessions.c.abs_expires_at > now,
            )
        )
    ).scalar_one()
