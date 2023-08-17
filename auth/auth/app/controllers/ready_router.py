"""Auth controller implementation."""
import logging

from auth.app.router import router

from classy_fastapi import Routable, get

log = logging.getLogger(__name__)


@router(prefix="/ready")
class ReadyRoutes(Routable):
    @get("")
    async def ready(self):
        """Return true if server is ready to serve requests."""
        return {"status": "OK"}
