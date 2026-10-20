"""Engines for the admin tests' fixtures.

A fixture engine is used for many statements in a test (the runner, the portal,
the settings service and the checks all go through it). With ``NullPool`` every
statement opened a new Postgres connection: a backend process, password
authentication and an SSL attempt, ~6 ms each against ~0.1 ms for the query,
which made connecting most of the admin suite's time. A small pool keeps the
connections of one test open, the way the services' own engines do in
production (``backend/admin/db.py`` pools too).

What a test can observe does not change: privileges are checked per statement,
the admin locks are row locks taken inside transactions (``admin.take_lock``)
or transaction-scoped advisory locks, and a returned connection is rolled back.
The engine is disposed when the fixture ends, before its database is dropped.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def fixture_engine(url: str) -> AsyncEngine:
    return create_async_engine(url, pool_size=2, max_overflow=8)
