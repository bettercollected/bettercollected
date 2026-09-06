"""Checkpoints for the migration engine (one row per collection).

Concrete class per service, beside its outbox row::

    class MigrationProgress(Base, MigrationProgressMixin):
        __tablename__ = "migration_progress"
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Integer, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

STATE_RUNNING = "running"
STATE_PAUSED = "paused"  # stopped at a checkpoint (budget, signal); re-run continues
STATE_DONE = "done"
STATE_ERROR = "error"


class MigrationProgressMixin:
    collection: Mapped[str] = mapped_column(Text, primary_key=True)
    last_id: Mapped[Optional[str]] = mapped_column(Text)  # highest _id copied so far
    count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    batch_size: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    state: Mapped[str] = mapped_column(Text, nullable=False, default=STATE_PAUSED)
    run_id: Mapped[Optional[str]] = mapped_column(Text)
    note: Mapped[Optional[str]] = mapped_column(Text)
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    updated_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
