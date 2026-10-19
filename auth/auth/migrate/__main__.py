"""python -m auth.migrate [--group auth] {preflight,backfill,verify,reconcile,status}

Runs as this service's role against its schema and Mongo database
(plans/postgres-consolidation.md §5). The service has one repository group,
``auth``; a clean ``verify`` records the "migration verified" marker
(``common.db.marker``).
"""

import os
import sys

import auth
from auth.config import settings
from auth.db.base import SCHEMA, Base
from auth.db.models import MigrationProgress, StoreMigration
import auth.db.models  # noqa: F401 — registers every row
from common.db.migrate import Target
from common.db.migrate.cli import code_version, main


def _tables():
    return {
        mapper.class_.mongo_collection(): mapper.local_table
        for mapper in Base.registry.mappers
        if hasattr(mapper.class_, "mongo_collection")
        and mapper.local_table.name
        not in ("mirror_write_failures", "migration_progress")
    }


def build_target(database_url: str) -> Target:
    return Target(
        schema=SCHEMA,
        tables=_tables(),
        progress=MigrationProgress.__table__,
        mongo_uri=settings.mongo_settings.URI,
        mongo_db=settings.mongo_settings.DB,
        database_url=database_url,
        application_name="bettercollected-migrate-" + SCHEMA,
        service="auth",
        groups={c: "auth" for c in _tables()},
        marker=StoreMigration.__table__,
        code_version=code_version(auth, SCHEMA),
    )


if __name__ == "__main__":
    target = build_target(os.environ["DATABASE_URL"])
    sys.exit(main(sys.argv[1:], target, prog="python -m auth.migrate"))
