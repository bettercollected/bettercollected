"""Process entry for the task runner service: ``python -m backend.admin.runner``.

Environment (nothing else is read): ``TASKS_DATABASE_URL`` (the ``bc_tasks``
role) and ``SETTINGS_MASTER_KEY`` (keys the request signatures and the audit
chain). Optional, for the responses data tasks: ``DATABASE_URL``, ``MONGO_URI``,
``MONGO_DB`` and ``MASTER_ENCRYPTION_KEYSET`` (a task refuses when they are
missing). ``ADMIN_TASKS_SELFTEST=1`` adds the test tasks. The process imports no
public-application module and never the shared crypto service.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from typing import Mapping, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from backend.admin.config import AdminConfigError, parse_database_url
from backend.admin.tasks import impl, signing
from backend.admin.tasks.registry import Registry
from backend.admin.tasks.runner.runner import POLL_SECONDS, Runner

DATABASE_URL_KEY = "TASKS_DATABASE_URL"


def make_engine(url: str) -> AsyncEngine:
    return create_async_engine(
        url,
        pool_size=5,
        max_overflow=0,
        pool_pre_ping=True,
        connect_args={"server_settings": {"statement_timeout": "30000"}},
    )


async def check_ready(engine: AsyncEngine) -> None:
    """Refuse to serve unless the ``tasks`` schema is there and readable."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1 FROM tasks.runs LIMIT 0"))


async def amain(env: Mapping[str, str] = os.environ, stop: Optional[asyncio.Event] = None) -> int:
    try:
        url = parse_database_url(env.get(DATABASE_URL_KEY))
        signing.request_key()  # fails fast on a missing or weak master key
    except AdminConfigError as e:
        message = str(e).replace("ADMIN_DATABASE_URL", DATABASE_URL_KEY)
        print(f"task runner cannot start: {message}", file=sys.stderr)
        return 2
    registry: Registry = impl.build_registry(env)
    engine = make_engine(url)
    stop = stop or asyncio.Event()
    loop = asyncio.get_running_loop()
    runner = Runner(engine, registry)
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda: (stop.set(), setattr(runner, "stopping", True)))
        except NotImplementedError:  # pragma: no cover - non-Unix
            pass
    try:
        await check_ready(engine)
        logging.getLogger("backend.admin.tasks").info(
            "task runner started id=%s tasks=%d", runner.runner_id, len(registry)
        )
        await runner.serve(stop, POLL_SECONDS)
    finally:
        await engine.dispose()
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
