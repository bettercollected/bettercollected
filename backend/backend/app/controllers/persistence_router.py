"""Operator view of the persistence layer (plans/postgres-consolidation.md §8).

Admin-only. The jobs backends in effect, whether Postgres answers, and that
Mongo is not used (Postgres is the only store since 4.1). The migration CLI's
`status` prints the import's picture; this is the live one.
"""

from classy_fastapi import get
from fastapi import Depends

from backend.app.container import container
from backend.app.router import router
from backend.app.services.user_service import get_logged_admin
from backend.app.utils.custom_routable import CustomRoutable
from backend.jobs.app import JOB_NAMES, postgres_jobs_enabled
from common.db import ping
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
        return {
            "flags": flags.describe(JOB_NAMES),
            "jobs_on_postgres": postgres_jobs_enabled(flags),
            "postgres": postgres,
            "mongo": {"used": False, "status": "not used"},
        }
