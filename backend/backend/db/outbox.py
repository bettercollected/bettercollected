"""The backend's outbox recorder: :class:`common.db.OutboxRecorder` bound to
the ``app.mirror_write_failures`` row (plans/postgres-consolidation.md §6)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.db.models import MirrorWriteFailure
from common.db import OutboxRecorder as _OutboxRecorder


class OutboxRecorder(_OutboxRecorder):
    def __init__(self, session_factory: Optional[async_sessionmaker[AsyncSession]]):
        super().__init__(session_factory, MirrorWriteFailure)
