"""python -m backend.migrate [--group G] {preflight,backfill,verify,reconcile,status,resolve-outbox,jobs-sweep}

Runs as the backend's role against schema ``app`` and Mongo database
``MONGO_DB``. ``--group`` selects the collections of repository groups
(``backend.db.groups.COLLECTION_GROUPS``); a clean ``verify`` records the
"migration verified" marker (``common.db.marker``). The groups served from
Postgres only (``POSTGRES_ONLY_GROUPS``) are imported with ``backfill``;
``verify`` and ``reconcile`` skip them, and refuse to be pointed at one. ``jobs-sweep``
(re)creates the scheduled response deletions on the chosen jobs backend —
independent of any queue's memory (plans §7, §9).
"""

import os
import sys

from bson import ObjectId

import backend
from backend.config import settings
from backend.db.base import SCHEMA
from backend.db.groups import (
    COLLECTION_GROUPS,
    POSTGRES_ONLY_GROUPS,
    load_backend_flags,
)
from backend.db.models import MigrationProgress, StoreMigration
from backend.db.mongo_import_guard import collection_tables as _tables
from common.db.migrate import Target
from common.db.migrate.cli import code_version, main


async def schedule_expirations(responses_repo, schedule) -> int:
    """Hand every response with an expiration to ``schedule``, read through the
    routed responses repository (so from ``DB_READ_SOURCE__responses``, the
    store the services read). Returns how many were scheduled."""
    from common.models.standard_form import StandardFormResponse

    scheduled = 0
    for response_id, expiration in await responses_repo.list_expiration_schedules():
        await schedule(
            StandardFormResponse(response_id=response_id, expiration=expiration)
        )
        scheduled += 1
    return scheduled


async def jobs_sweep(backend: str) -> dict:
    """Every response with an expiration gets its deletion (re)scheduled on
    ``backend``; queueing locks / schedule ids make this idempotent."""
    from backend.app.services.temporal_service import TemporalService
    from backend.cli_store import routed_repositories
    from backend.jobs.app import app as jobs_app
    from common.db import load_flags

    async with routed_repositories("responses") as container:
        service = TemporalService(
            server_uri=settings.temporal_settings.server_uri,
            namespace=settings.temporal_settings.namespace,
            crypto=container.crypto(),
            flags=load_flags({"JOBS_BACKEND__delete_response": backend}),
            jobs=jobs_app,
        )
        async with jobs_app.open_async():
            scheduled = await schedule_expirations(
                container.form_response_repo(),
                service.add_scheduled_job_for_deleting_response,
            )
    return {
        "backend": backend,
        "read_from": container.flags().read_source("responses").value,
        "scheduled": scheduled,
    }


def repository_groups() -> dict:
    """Routed repository name -> group, for ``resolve-outbox`` (an outbox
    entry names the repository, not the group)."""
    from backend.app.container import AppContainer
    from common.db.migrate.outbox import routed_repository_groups

    return routed_repository_groups(AppContainer)


def build_target(database_url: str) -> Target:
    return Target(
        schema=SCHEMA,
        tables=_tables(),
        progress=MigrationProgress.__table__,
        mongo_uri=settings.mongo_settings.URI,
        mongo_db=settings.mongo_settings.DB,
        database_url=database_url,
        application_name="bettercollected-migrate-backend",
        extras={"jobs_sweep": jobs_sweep},
        service="backend",
        groups=COLLECTION_GROUPS,
        repository_groups=repository_groups,
        marker=StoreMigration.__table__,
        code_version=code_version(backend, SCHEMA),
        postgres_only_groups=POSTGRES_ONLY_GROUPS,
        load_flags=load_backend_flags,
    )


if __name__ == "__main__":
    target = build_target(os.environ["DATABASE_URL"])
    sys.exit(main(sys.argv[1:], target, prog="python -m backend.migrate"))
