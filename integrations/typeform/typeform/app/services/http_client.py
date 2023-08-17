import logging
import typing

from httpx import AsyncClient

log = logging.getLogger(__name__)


class HttpClient(AsyncClient):
    async def get(self, *args, **kwargs) -> typing.Any:
        response = await super().get(*args, **kwargs)
        return response.json()
