import datetime

from starlette.middleware.cors import CORSMiddleware
from starlette.types import Receive, Scope, Send



async def _allowed_origins() -> list[str]:
    # Resolved at call time: the container imports services that import this module.
    from backend.app.container import container

    return await container.allowed_origins_repo().list_origins()


class DynamicCORSMiddleware(CORSMiddleware):
    _allowed_origins: list[str] = []
    _cache_refreshed_at: datetime.datetime = datetime.datetime.min.replace(
        tzinfo=datetime.timezone.utc
    )
    _cache_ttl_seconds: float = 60 * 60

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            await self._refresh_origins_if_stale()
        await super().__call__(scope, receive, send)

    async def _refresh_origins_if_stale(self) -> None:
        now = datetime.datetime.now(datetime.timezone.utc)
        if (now - self._cache_refreshed_at).total_seconds() < self._cache_ttl_seconds:
            return
        DynamicCORSMiddleware._allowed_origins = await _allowed_origins()
        DynamicCORSMiddleware._cache_refreshed_at = now

    @classmethod
    async def force_refresh_origins(cls) -> None:
        """Force reload allowed origins from the database, bypassing the cache TTL."""
        cls._allowed_origins = await _allowed_origins()
        cls._cache_refreshed_at = datetime.datetime.now(datetime.timezone.utc)

    def is_allowed_origin(self, origin: str) -> bool:
        return origin in self._allowed_origins
