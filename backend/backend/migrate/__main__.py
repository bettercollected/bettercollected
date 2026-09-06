"""python -m backend.migrate {preflight,backfill,verify,reconcile,status,jobs-sweep}

Runs as the backend's role against schema ``app`` and Mongo database
``MONGO_DB``. ``jobs-sweep`` (re)creates the scheduled response deletions on
the chosen jobs backend — independent of any queue's memory (plans §7, §9).
"""

import os
import sys

from bson import ObjectId

from backend.config import settings
from backend.db.base import SCHEMA, Base
from backend.db.models import MigrationProgress
import backend.db.models  # noqa: F401 — registers every row
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


async def jobs_sweep(backend: str) -> dict:
    """Every response with an expiration gets its deletion (re)scheduled on
    ``backend``; queueing locks / schedule ids make this idempotent."""
    from pymongo import AsyncMongoClient

    from backend.app.container import container
    from backend.app.services.temporal_service import TemporalService
    from backend.jobs.app import app as jobs_app
    from common.db import load_flags
    from common.models.standard_form import StandardFormResponse

    service = TemporalService(
        server_uri=settings.temporal_settings.server_uri,
        namespace=settings.temporal_settings.namespace,
        crypto=container.crypto(),
        flags=load_flags({"JOBS_BACKEND__delete_response": backend}),
        jobs=jobs_app,
    )
    client = AsyncMongoClient(settings.mongo_settings.URI)
    responses = client[settings.mongo_settings.DB]["form_responses"]
    scheduled = 0
    async with jobs_app.open_async():
        async for doc in responses.find(
            {
                "expiration_type": {"$in": ["date", "days"]},
                "expiration": {"$type": "string"},
            },
            {"response_id": 1, "expiration": 1},
        ):
            await service.add_scheduled_job_for_deleting_response(
                StandardFormResponse(
                    response_id=doc["response_id"], expiration=doc["expiration"]
                )
            )
            scheduled += 1
    await client.close()
    return {"backend": backend, "scheduled": scheduled}


if __name__ == "__main__":
    target = Target(
        schema=SCHEMA,
        tables=_tables(),
        progress=MigrationProgress.__table__,
        mongo_uri=settings.mongo_settings.URI,
        mongo_db=settings.mongo_settings.DB,
        database_url=os.environ["DATABASE_URL"],
        application_name="bettercollected-migrate-backend",
        extras={"jobs_sweep": jobs_sweep},
    )
    sys.exit(main(sys.argv[1:], target, prog="python -m backend.migrate"))
