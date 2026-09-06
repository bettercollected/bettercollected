"""Postgres engine/session providers for the backend container — thin wrappers
over :mod:`common.db.runtime`, which every service shares (the backend grew
them first). Everything is a no-op when ``DATABASE_URL`` is unset.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncEngine

from common.db import (
    DatabaseSettings,
    LazyRepository,
    postgres_repository,
)  # noqa: F401
from common.db import build_engine as _build_engine
from common.db import build_sessionmaker  # noqa: F401

APPLICATION_NAME = "bettercollected-backend"


def build_engine(settings: DatabaseSettings) -> Optional[AsyncEngine]:
    return _build_engine(settings, APPLICATION_NAME)
