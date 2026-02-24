import datetime

from starlette.middleware.cors import CORSMiddleware
from starlette.types import Receive, Scope, Send

from backend.app.schemas.allowed_origin import AllowedOriginsDocument


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
        docs = await AllowedOriginsDocument.find().to_list()
        DynamicCORSMiddleware._allowed_origins = [doc.origin for doc in docs]
        DynamicCORSMiddleware._cache_refreshed_at = now

    def is_allowed_origin(self, origin: str) -> bool:
        return origin in self._allowed_origins
