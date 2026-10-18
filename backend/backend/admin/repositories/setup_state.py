"""SQL for the first-run setup state (SQLAlchemy Core, no policy).

One row at most: written when a setup token is redeemed, closed when the
operator finishes the checklist. Every function takes the caller's connection.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from backend.admin.repositories.tables import setup_state


async def get(conn: AsyncConnection):
    return (await conn.execute(select(setup_state))).first()


async def start(conn: AsyncConnection, started_by: str, now: datetime) -> None:
    """Record that the setup began (a second start keeps the first row)."""
    await conn.execute(
        insert(setup_state)
        .values(started_by=started_by, started_at=now)
        .on_conflict_do_nothing(index_elements=[setup_state.c.singleton])
    )


async def set_mail_step(conn: AsyncConnection, step: str, now: datetime) -> bool:
    result = await conn.execute(
        update(setup_state)
        .where(setup_state.c.completed_at.is_(None))
        .values(mail_step=step, mail_step_at=now)
    )
    return result.rowcount == 1


async def complete(conn: AsyncConnection, by: str, now: datetime) -> bool:
    """Close the setup; False when it was already closed (or never started)."""
    result = await conn.execute(
        update(setup_state)
        .where(setup_state.c.completed_at.is_(None))
        .values(completed_at=now, completed_by=by)
    )
    return result.rowcount == 1
