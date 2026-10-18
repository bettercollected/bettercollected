"""SQL for the audit log (SQLAlchemy Core). No hashing or masking here."""

from __future__ import annotations

from datetime import datetime
from typing import Any, AsyncIterator, Mapping, Optional

from sqlalchemy import null, select, text
from sqlalchemy.ext.asyncio import AsyncConnection

from backend.admin.repositories.tables import audit_log

# Same value as CHAIN_LOCK_KEY in migration 0003; the insert trigger takes it too.
CHAIN_LOCK_KEY = -1909258384265368190

JSON_COLUMNS = ("before", "after", "detail")


async def lock_chain(conn: AsyncConnection) -> None:
    """Serialise chain writers until the caller's transaction ends."""
    await conn.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": CHAIN_LOCK_KEY})


async def head_and_now(conn: AsyncConnection) -> tuple[Optional[bytes], datetime]:
    row = (
        await conn.execute(
            text(
                "SELECT (SELECT row_hash FROM admin.audit_log ORDER BY seq DESC LIMIT 1), "
                "clock_timestamp()"
            )
        )
    ).one()
    return (bytes(row[0]) if row[0] is not None else None), row[1]


async def insert(conn: AsyncConnection, values: Mapping[str, Any]) -> int:
    row = {
        k: (null() if k in JSON_COLUMNS and v is None else v) for k, v in values.items()
    }
    result = await conn.execute(
        audit_log.insert().values(**row).returning(audit_log.c.seq)
    )
    return result.scalar_one()


async def stream_rows(
    conn: AsyncConnection, batch_size: int = 1000
) -> AsyncIterator[Any]:
    result = await conn.stream(
        select(audit_log)
        .order_by(audit_log.c.seq)
        .execution_options(yield_per=batch_size)
    )
    async for row in result:
        yield row
