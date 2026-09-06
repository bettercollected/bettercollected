"""python -m googleform.migrate {preflight,backfill,verify,reconcile,status}

Runs as this service's role against its schema and Mongo database
(plans/postgres-consolidation.md §5).
"""

import os
import sys

from googleform.config import settings
from googleform.db.base import SCHEMA, Base
from googleform.db.models import MigrationProgress
import googleform.db.models  # noqa: F401 — registers every row
from common.db.migrate import Target
from common.db.migrate.cli import main


def _tables():
    return {
        mapper.class_.mongo_collection(): mapper.local_table
        for mapper in Base.registry.mappers
        if hasattr(mapper.class_, "mongo_collection")
        and mapper.local_table.name
        not in ("mirror_write_failures", "migration_progress")
    }


if __name__ == "__main__":
    target = Target(
        schema=SCHEMA,
        tables=_tables(),
        progress=MigrationProgress.__table__,
        mongo_uri=settings.mongo_settings.URI,
        mongo_db=settings.mongo_settings.DB,
        database_url=os.environ["DATABASE_URL"],
        application_name="bettercollected-migrate-" + SCHEMA,
    )
    sys.exit(main(sys.argv[1:], target, prog="python -m googleform.migrate"))
