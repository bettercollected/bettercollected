"""python -m googleform.migrate [--group google] {preflight,backfill,verify,reconcile,status,resolve-outbox}

Runs as this service's role against its schema and Mongo database
(plans/postgres-consolidation.md §5). The service has one repository group,
``google``; a clean ``verify`` records the "migration verified" marker
(``common.db.marker``).
"""

import os
import sys

import googleform
from googleform.config import settings
from googleform.db.base import SCHEMA
from googleform.db.import_guard import collection_tables as _tables
from googleform.db.models import MigrationProgress, StoreMigration
import googleform.db.models  # noqa: F401 — registers every row
from common.db.migrate import Target
from common.db.migrate.cli import code_version, main


def build_target(database_url: str) -> Target:
    return Target(
        schema=SCHEMA,
        tables=_tables(),
        progress=MigrationProgress.__table__,
        mongo_uri=settings.mongo_settings.URI,
        mongo_db=settings.mongo_settings.DB,
        database_url=database_url,
        application_name="bettercollected-migrate-" + SCHEMA,
        service="google",
        groups={c: "google" for c in _tables()},
        marker=StoreMigration.__table__,
        code_version=code_version(googleform, SCHEMA),
    )


if __name__ == "__main__":
    target = build_target(os.environ["DATABASE_URL"])
    sys.exit(main(sys.argv[1:], target, prog="python -m googleform.migrate"))
