"""SQL for the audit log (SQLAlchemy Core). No hashing or masking here."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, AsyncIterator, Mapping, Optional

from sqlalchemy import null, select, text
from sqlalchemy.ext.asyncio import AsyncConnection

from backend.admin.repositories.tables import audit_log

JSON_COLUMNS = ("before", "after", "detail")


async def lock_chain(conn: AsyncConnection) -> None:
    """Serialise chain writers until the caller's transaction ends: the row lock
    ``audit_chain`` (migration 0013), which only the admin roles can take. The
    insert trigger takes the same lock. Gives up after 5 s with SQLSTATE 55P03."""
    await conn.execute(text("SELECT admin.take_lock('audit_chain')"))


async def head_and_now(
    conn: AsyncConnection,
) -> tuple[Optional[bytes], Optional[int], datetime]:
    """(latest row_hash, latest seq, database clock); the first two are ``None``
    for an empty log."""
    row = (
        await conn.execute(
            text(
                "SELECT h.row_hash, h.seq, clock_timestamp() "
                "FROM (SELECT 1) one LEFT JOIN LATERAL "
                "(SELECT row_hash, seq FROM admin.audit_log ORDER BY seq DESC LIMIT 1) h ON true"
            )
        )
    ).one()
    return (bytes(row[0]) if row[0] is not None else None), row[1], row[2]


async def runner_begin(
    conn: AsyncConnection, settings_lock: bool
) -> tuple[Optional[bytes], Optional[int], datetime]:
    """The runner's way to the chain head: ``tasks.begin_audit`` takes the locks
    (the settings writer's first when asked) and returns the head hash, its seq and
    the database clock; the runner's role cannot read the log itself."""
    row = (
        await conn.execute(
            text("SELECT o_head, o_seq, o_now FROM tasks.begin_audit(:s)"),
            {"s": settings_lock},
        )
    ).one()
    return (bytes(row[0]) if row[0] is not None else None), row[1], row[2]


def json_param(value: Any) -> Optional[str]:
    return None if value is None else json.dumps(value, allow_nan=False)


async def runner_append(conn: AsyncConnection, values: Mapping[str, Any]) -> int:
    """Append a runner row through ``tasks.audit_append`` (fixed action kinds, checks
    the run's state; see migration 0015)."""
    return (
        await conn.execute(
            text(
                "SELECT tasks.audit_append(:action, :tt, :tid, :outcome, "
                "CAST(CAST(:before AS text) AS jsonb), CAST(CAST(:after AS text) AS jsonb), "
                "CAST(CAST(:detail AS text) AS jsonb), :rid, :id, :at, :prev, :hash, :kv)"
            ),
            {
                "action": values["action"],
                "tt": values["target_type"],
                "tid": values["target_id"],
                "outcome": values["outcome"],
                "before": json_param(values["before"]),
                "after": json_param(values["after"]),
                "detail": json_param(values["detail"]),
                "rid": values["request_id"],
                "id": values["id"],
                "at": values["at"],
                "prev": values["prev_hash"],
                "hash": values["row_hash"],
                "kv": values["key_version"],
            },
        )
    ).scalar_one()


async def insert(conn: AsyncConnection, values: Mapping[str, Any]) -> int:
    row = {
        k: (null() if k in JSON_COLUMNS and v is None else v) for k, v in values.items()
    }
    result = await conn.execute(
        audit_log.insert().values(**row).returning(audit_log.c.seq)
    )
    return result.scalar_one()


async def get_verify_state(conn: AsyncConnection) -> Optional[tuple[int, bytes, int]]:
    """(verified seq, its row_hash, rows verified so far) or ``None`` before the first pass."""
    row = (
        await conn.execute(
            text(
                "SELECT verified_seq, verified_hash, rows_verified "
                "FROM admin.audit_verify_state WHERE id = 1"
            )
        )
    ).first()
    return None if row is None else (row[0], bytes(row[1]), row[2])


async def save_verify_state(
    conn: AsyncConnection, seq: int, row_hash: bytes, rows: int
) -> None:
    await conn.execute(
        text(
            "INSERT INTO admin.audit_verify_state AS s (id, verified_seq, verified_hash, rows_verified) "
            "VALUES (1, :seq, :hash, :rows) ON CONFLICT (id) DO UPDATE SET "
            "verified_seq = excluded.verified_seq, verified_hash = excluded.verified_hash, "
            "rows_verified = s.rows_verified + excluded.rows_verified, "
            "verified_at = clock_timestamp()"
        ),
        {"seq": seq, "hash": row_hash, "rows": rows},
    )


async def row_hash_at(conn: AsyncConnection, seq: int) -> Optional[bytes]:
    value = (
        await conn.execute(
            text("SELECT row_hash FROM admin.audit_log WHERE seq = :s"), {"s": seq}
        )
    ).scalar_one_or_none()
    return None if value is None else bytes(value)


async def rows_after(conn: AsyncConnection, seq: int, limit: int) -> list:
    return list(
        (
            await conn.execute(
                select(audit_log)
                .where(audit_log.c.seq > seq)
                .order_by(audit_log.c.seq)
                .limit(limit)
            )
        ).all()
    )


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
