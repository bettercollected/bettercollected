"""Operator view of the Mongo → Postgres cutover (plans/postgres-consolidation.md §8).

Admin-only. What the flags route where, the routing counters since boot
(calls, mirror failures, shadow reads/diffs/errors, per group and method),
the outbox backlog in both stores, whether Postgres answers and whether Mongo
is used at all (it is not once every group is on Postgres). The migration
CLI's `status` prints the same picture; this is the live one.
"""

from classy_fastapi import get
from fastapi import Depends

from backend.app.container import container
from backend.app.router import router
from backend.app.services.user_service import get_logged_admin
from backend.app.utils.custom_routable import CustomRoutable
from backend.db.models import MirrorWriteFailure
from backend.db.startup import GROUPS, mongo_required
from backend.jobs.app import JOB_NAMES, postgres_jobs_enabled
from common.db import metrics_snapshot, mongo_status, outbox_backlog, ping
from common.models.user import User


@router(prefix="/persistence", tags=["Persistence"])
class PersistenceRouter(CustomRoutable):
    @get("/status")
    async def status(self, user: User = Depends(get_logged_admin)):
        flags = container.flags()
        engine = container.pg_engine()
        postgres = {"configured": engine is not None, "reachable": None}
        if engine is not None:
            try:
                await ping(engine)
                postgres["reachable"] = True
            except Exception as exc:  # noqa: BLE001 — reported, never raised
                postgres["reachable"] = False
                postgres["error"] = type(exc).__name__
        mongo_used = mongo_required(container)
        return {
            "flags": flags.describe(GROUPS, JOB_NAMES),
            "jobs_on_postgres": postgres_jobs_enabled(flags),
            "postgres": postgres,
            "mongo": mongo_status(mongo_used),
            "metrics": metrics_snapshot(container.routing_metrics()),
            "outbox": await outbox_backlog(
                container.pg_sessionmaker(), MirrorWriteFailure, mongo_used=mongo_used
            ),
        }
