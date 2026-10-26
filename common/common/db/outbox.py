"""The outbox table of mirror writes that failed while 4.0 ran both stores.

Nothing writes it any more (the services have no mirror since 4.1). The
per-schema table declared from :class:`MirrorWriteFailureMixin`
(``<schema>.mirror_write_failures``) stays for the import from 4.0:
``resolve-outbox`` (``python -m <service>.migrate``) reads and resolves the
entries a 4.0 stack left behind. The tables are dropped with the other
dual-run leftovers in 5.x.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

MIRROR_OPS = ("insert", "update", "delete")


class MirrorWriteFailureMixin:
    """Columns of the Postgres-side outbox. Concrete class per service:

    class MirrorWriteFailure(Base, MirrorWriteFailureMixin):
        __tablename__ = "mirror_write_failures"
    """

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(Text, nullable=False)
    row_id: Mapped[str] = mapped_column(Text, nullable=False)
    op: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str] = mapped_column(Text, nullable=False)
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
