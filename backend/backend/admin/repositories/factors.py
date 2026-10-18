"""SQL for second factors, recovery codes and the addresses an admin signed in
from (SQLAlchemy Core, no policy).

Every function takes the caller's connection so a service can put an action and
its audit row in one transaction. Times are passed in.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Sequence

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from backend.admin.repositories.tables import factors, recovery_codes, sessions

RECENT_SESSIONS = 20


async def insert_factor(
    conn: AsyncConnection, factor_id: uuid.UUID, email: str, blob: str, key_id: str,
    now: datetime,
) -> None:
    await conn.execute(
        factors.insert().values(
            id=factor_id, email=email, secret_blob=blob, key_id=key_id, created_at=now
        )
    )


async def lock_for_update(conn: AsyncConnection, email: str) -> None:
    """Serialise changes to one admin's factors: ``FOR UPDATE`` on their rows, so
    two enrolments cannot both end up confirmed (the second then sees the first)."""
    await conn.execute(
        select(factors.c.id).where(factors.c.email == email).order_by(factors.c.id).with_for_update()
    )


async def get_by_id(conn: AsyncConnection, factor_id: uuid.UUID):
    return (await conn.execute(select(factors).where(factors.c.id == factor_id))).first()


async def get_confirmed(conn: AsyncConnection, email: str):
    """The admin's confirmed factor (at most one is kept), or None."""
    return (
        await conn.execute(
            select(factors)
            .where(factors.c.email == email, factors.c.confirmed_at.is_not(None))
            .order_by(factors.c.confirmed_at.desc())
            .limit(1)
        )
    ).first()


async def get_pending(conn: AsyncConnection, factor_id: uuid.UUID, email: str):
    return (
        await conn.execute(
            select(factors).where(
                factors.c.id == factor_id,
                factors.c.email == email,
                factors.c.confirmed_at.is_(None),
            )
        )
    ).first()


async def delete_pending(conn: AsyncConnection, email: str) -> int:
    result = await conn.execute(
        delete(factors).where(factors.c.email == email, factors.c.confirmed_at.is_(None))
    )
    return int(result.rowcount or 0)


async def delete_confirmed_except(
    conn: AsyncConnection, email: str, keep: uuid.UUID
) -> int:
    """Drop the admin's older confirmed factors (their recovery codes go with
    them by the foreign key's cascade)."""
    result = await conn.execute(
        delete(factors).where(
            factors.c.email == email,
            factors.c.confirmed_at.is_not(None),
            factors.c.id != keep,
        )
    )
    return int(result.rowcount or 0)


async def delete_all(conn: AsyncConnection, email: str) -> int:
    """Every factor of ``email`` (codes cascade): the break-glass reset."""
    result = await conn.execute(delete(factors).where(factors.c.email == email))
    return int(result.rowcount or 0)


async def confirm(
    conn: AsyncConnection, factor_id: uuid.UUID, email: str, now: datetime, step: int
) -> bool:
    """Mark a pending factor confirmed (and its first code used); True for
    exactly one caller."""
    result = await conn.execute(
        update(factors)
        .where(
            factors.c.id == factor_id,
            factors.c.email == email,
            factors.c.confirmed_at.is_(None),
        )
        .values(confirmed_at=now, last_used_step=step)
        .returning(factors.c.id)
    )
    return result.scalar_one_or_none() is not None


async def advance_step(conn: AsyncConnection, factor_id: uuid.UUID, step: int) -> bool:
    """Replay guard (the contract in ``security/totp.py``): True only when the
    step is newer than every one accepted before, for exactly one caller."""
    result = await conn.execute(
        update(factors)
        .where(
            factors.c.id == factor_id,
            (factors.c.last_used_step.is_(None)) | (factors.c.last_used_step < step),
        )
        .values(last_used_step=step)
        .returning(factors.c.id)
    )
    return result.scalar_one_or_none() is not None


# -- recovery codes ------------------------------------------------------------


async def insert_recovery(
    conn: AsyncConnection, factor_id: uuid.UUID, hashes: Sequence[bytes], now: datetime
) -> None:
    await conn.execute(
        recovery_codes.insert(),
        [{"code_hash": h, "factor_id": factor_id, "created_at": now} for h in hashes],
    )


async def delete_recovery(conn: AsyncConnection, factor_id: uuid.UUID) -> int:
    result = await conn.execute(
        delete(recovery_codes).where(recovery_codes.c.factor_id == factor_id)
    )
    return int(result.rowcount or 0)


async def unused_hashes(conn: AsyncConnection, factor_id: uuid.UUID) -> list:
    rows = await conn.execute(
        select(recovery_codes.c.code_hash).where(
            recovery_codes.c.factor_id == factor_id, recovery_codes.c.used_at.is_(None)
        )
    )
    return [bytes(r[0]) for r in rows]


async def burn_recovery(conn: AsyncConnection, code_hash: bytes, now: datetime) -> bool:
    """Single use: True for exactly one caller."""
    result = await conn.execute(
        update(recovery_codes)
        .where(recovery_codes.c.code_hash == code_hash, recovery_codes.c.used_at.is_(None))
        .values(used_at=now)
        .returning(recovery_codes.c.code_hash)
    )
    return result.scalar_one_or_none() is not None


async def count_unused(conn: AsyncConnection, factor_id: uuid.UUID) -> int:
    return int(
        (
            await conn.execute(
                select(func.count())
                .select_from(recovery_codes)
                .where(
                    recovery_codes.c.factor_id == factor_id,
                    recovery_codes.c.used_at.is_(None),
                )
            )
        ).scalar()
    )


# -- addresses ------------------------------------------------------------------


async def recent_session_ips(
    conn: AsyncConnection, email: str, exclude: uuid.UUID, limit: int = RECENT_SESSIONS
) -> set:
    """The distinct addresses of the admin's last ``limit`` other sessions
    (the sessions table is the only record; nothing new is stored)."""
    rows = await conn.execute(
        select(sessions.c.ip)
        .where(
            sessions.c.email == email,
            sessions.c.id != exclude,
            sessions.c.mfa_state == "mfa_ok",  # an address that never passed the factor proves nothing
        )
        .order_by(sessions.c.created_at.desc())
        .limit(limit)
    )
    return {str(r[0]) for r in rows if r[0] is not None}
