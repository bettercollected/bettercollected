"""Record mirror-write failures in the *primary* store (plans/postgres-consolidation.md §6).

The routing layer calls this when replaying a write on the mirror store fails.
While Mongo is primary the record is a ``MirrorWriteFailureDocument``; once
Postgres is primary it is a row in ``app.mirror_write_failures``. The
reconciler (migration CLI) drains both.
"""

from __future__ import annotations

from typing import Optional

from beanie import Document
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.db.models import MirrorWriteFailure
from common.db import MirrorFailure, MirrorWriteFailureDocument, ReadSource

MAX_IDS = 20


def _ids(args: tuple, kwargs: dict) -> str:
    """Best-effort: the ids a call touched, from document / id-like arguments."""
    found: list[str] = []
    for value in list(args) + list(kwargs.values()):
        if isinstance(value, Document):
            if value.id is not None:
                found.append(str(value.id))
        elif type(value).__name__ in ("ObjectId", "PydanticObjectId"):
            found.append(str(value))
        elif isinstance(value, str) and len(value) <= 64:
            found.append(value)
        elif isinstance(value, (list, tuple)):
            for item in list(value)[:MAX_IDS]:
                if isinstance(item, Document) and item.id is not None:
                    found.append(str(item.id))
                elif isinstance(item, str) and len(item) <= 64:
                    found.append(item)
    return ",".join(found[:MAX_IDS]) or "-"


def _error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


class OutboxRecorder:
    def __init__(self, session_factory: Optional[async_sessionmaker[AsyncSession]]):
        self._sessions = session_factory

    async def __call__(self, failure: MirrorFailure) -> None:
        row_id = _ids(failure.args + tuple(failure.documents), failure.kwargs)
        if failure.store is ReadSource.POSTGRES:
            # the mirror was Postgres, so Mongo is primary: record there
            await MirrorWriteFailureDocument(
                table_name=failure.repository,
                row_id=row_id,
                op=failure.method,
                error=_error(failure.error),
            ).insert()
            return
        if self._sessions is None:
            logger.error(
                "mirror to Mongo failed and Postgres is not configured to record it: {} {}",
                failure.repository,
                failure.method,
            )
            return
        async with self._sessions() as session, session.begin():
            session.add(
                MirrorWriteFailure(
                    table_name=failure.repository,
                    row_id=row_id,
                    op=failure.method,
                    error=_error(failure.error),
                )
            )
