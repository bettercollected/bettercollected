"""The procrastinate application: one per process, connected lazily.

Constructing the App does not connect; ``open_async`` does, and the backend
only opens it when some job kind is routed to Postgres. The queue tables live
in the ``jobs`` schema (postgres/init): the connection pins ``search_path`` to
it so procrastinate's unqualified table names resolve there for every role.
"""

from __future__ import annotations

import os

from procrastinate import App, PsycopgConnector

from common.db.flags import DbFlags, JobsBackend

DEFAULT_QUEUE = "default"
ACTIONS_QUEUE = "actions"
JOB_NAMES = ("delete_user", "delete_response", "run_action")
SEARCH_PATH_OPTIONS = "-c search_path=jobs"


def libpq_url(url: str) -> str:
    """``postgresql+asyncpg://…`` (SQLAlchemy) → ``postgresql://…`` (libpq/psycopg)."""
    scheme, _, rest = url.partition("://")
    return f"{scheme.split('+')[0]}://{rest}"


def build_connector(database_url: str | None) -> PsycopgConnector:
    return PsycopgConnector(
        conninfo=libpq_url(database_url) if database_url else "",
        kwargs={"options": SEARCH_PATH_OPTIONS},
        min_size=int(os.environ.get("JOBS_POOL_MIN", "1")),
        max_size=int(os.environ.get("JOBS_POOL_MAX", "4")),
    )


def postgres_jobs_enabled(flags: DbFlags) -> bool:
    return any(flags.jobs_backend(job) is JobsBackend.POSTGRES for job in JOB_NAMES)


app = App(
    connector=build_connector(os.environ.get("DATABASE_URL")),
    import_paths=["backend.jobs.tasks"],
)
