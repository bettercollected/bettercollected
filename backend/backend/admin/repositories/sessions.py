"""SQL for sessions and sign-in challenges (SQLAlchemy Core, no policy).

Every function takes the caller's connection, so a service can put an action
and its audit row in one transaction. Times are passed in, never read from the
database clock, so tests can move time by hand.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional, Sequence

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from backend.admin.repositories.tables import sessions, signin_challenges

# -- sessions -------------------------------------------------------------------


async def insert_session(conn: AsyncConnection, **values: Any) -> uuid.UUID:
    result = await conn.execute(sessions.insert().values(**values).returning(sessions.c.id))
    return result.scalar_one()


async def get_by_token_hash(conn: AsyncConnection, token_hash: bytes):
    return (
        await conn.execute(select(sessions).where(sessions.c.token_hash == token_hash))
    ).first()


async def get_by_id(conn: AsyncConnection, session_id: uuid.UUID):
    return (
        await conn.execute(select(sessions).where(sessions.c.id == session_id))
    ).first()


def _live(now: datetime):
    return and_(
        sessions.c.revoked_at.is_(None),
        sessions.c.idle_expires_at > now,
        sessions.c.abs_expires_at > now,
    )


async def list_live(conn: AsyncConnection, email: str, now: datetime):
    """Live sessions of ``email``, oldest first."""
    query = (
        select(sessions)
        .where(sessions.c.email == email, _live(now))
        .order_by(sessions.c.created_at, sessions.c.id)
    )
    return (await conn.execute(query)).all()


async def list_live_all(conn: AsyncConnection, now: datetime):
    return (await conn.execute(select(sessions).where(_live(now)))).all()


async def revoke(
    conn: AsyncConnection,
    session_ids: Sequence[uuid.UUID],
    now: datetime,
    reason: str,
    by: Optional[str],
) -> list:
    """Revoke the still-unrevoked sessions among ``session_ids``; returns the
    rows that changed (id, email)."""
    if not session_ids:
        return []
    result = await conn.execute(
        update(sessions)
        .where(sessions.c.id.in_(list(session_ids)), sessions.c.revoked_at.is_(None))
        .values(revoked_at=now, revoked_reason=reason, revoked_by=by)
        .returning(sessions.c.id, sessions.c.email)
    )
    return list(result.all())


async def touch(
    conn: AsyncConnection,
    session_id: uuid.UUID,
    last_seen: datetime,
    idle_expires: datetime,
) -> None:
    await conn.execute(
        update(sessions)
        .where(sessions.c.id == session_id, sessions.c.revoked_at.is_(None))
        .values(last_seen_at=last_seen, idle_expires_at=idle_expires)
    )


async def promote(
    conn: AsyncConnection,
    session_id: uuid.UUID,
    old_hash: bytes,
    new_hash: bytes,
    now: datetime,
    idle_expires: datetime,
):
    """Move a live session to ``mfa_ok`` under a new token hash, only while the
    old hash still matches (a replayed or stale call changes nothing)."""
    result = await conn.execute(
        update(sessions)
        .where(
            sessions.c.id == session_id,
            sessions.c.token_hash == old_hash,
            sessions.c.revoked_at.is_(None),
        )
        .values(
            token_hash=new_hash,
            mfa_state="mfa_ok",
            stepup_at=now,
            last_seen_at=now,
            idle_expires_at=idle_expires,
        )
        .returning(sessions.c.id)
    )
    return result.scalar_one_or_none()


async def set_stepup(conn: AsyncConnection, session_id: uuid.UUID, now: datetime) -> None:
    await conn.execute(
        update(sessions).where(sessions.c.id == session_id).values(stepup_at=now)
    )


async def delete_finished(conn: AsyncConnection, before: datetime) -> int:
    """Delete sessions that ended (revoked or expired) before ``before``."""
    ended = or_(
        sessions.c.revoked_at < before,
        and_(sessions.c.abs_expires_at < before),
        and_(sessions.c.idle_expires_at < before),
    )
    return int((await conn.execute(delete(sessions).where(ended))).rowcount or 0)


# -- challenges -----------------------------------------------------------------


async def kill_open_challenges(conn: AsyncConnection, email: str, now: datetime) -> int:
    """A new code request kills the previous code of the same address."""
    result = await conn.execute(
        update(signin_challenges)
        .where(
            signin_challenges.c.email == email,
            signin_challenges.c.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )
    return int(result.rowcount or 0)


async def insert_challenge(conn: AsyncConnection, **values: Any) -> uuid.UUID:
    result = await conn.execute(
        signin_challenges.insert().values(**values).returning(signin_challenges.c.id)
    )
    return result.scalar_one()


async def get_challenge(conn: AsyncConnection, challenge_id: uuid.UUID):
    return (
        await conn.execute(
            select(signin_challenges).where(signin_challenges.c.id == challenge_id)
        )
    ).first()


async def add_failed_attempt(conn: AsyncConnection, challenge_id: uuid.UUID) -> None:
    await conn.execute(
        update(signin_challenges)
        .where(signin_challenges.c.id == challenge_id)
        .values(failed_attempts=signin_challenges.c.failed_attempts + 1)
    )


async def consume_challenge(
    conn: AsyncConnection, challenge_id: uuid.UUID, now: datetime
) -> bool:
    """Atomically mark a live challenge used; True for exactly one caller."""
    result = await conn.execute(
        update(signin_challenges)
        .where(
            signin_challenges.c.id == challenge_id,
            signin_challenges.c.consumed_at.is_(None),
            signin_challenges.c.expires_at > now,
        )
        .values(consumed_at=now)
        .returning(signin_challenges.c.id)
    )
    return result.scalar_one_or_none() is not None


async def burn_challenge(
    conn: AsyncConnection, challenge_id: uuid.UUID, now: datetime
) -> None:
    await conn.execute(
        update(signin_challenges)
        .where(
            signin_challenges.c.id == challenge_id,
            signin_challenges.c.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )


async def delete_old_challenges(conn: AsyncConnection, before: datetime) -> int:
    result = await conn.execute(
        delete(signin_challenges).where(signin_challenges.c.expires_at < before)
    )
    return int(result.rowcount or 0)


async def count_challenges(conn: AsyncConnection) -> int:
    return int(
        (await conn.execute(select(func.count()).select_from(signin_challenges))).scalar()
    )
