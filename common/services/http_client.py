import logging
import typing

from httpx import AsyncClient

from common.exceptions.http import HTTPException
from common.constants import messages

log = logging.getLogger(__name__)


class HttpClient(AsyncClient):
    async def get(self, *args, **kwargs) -> typing.Mapping[str, typing.Any]:
        response = await super().get(*args, **kwargs)
        if response.status_code != 200:
            logging.error(
                f"Response status: {response.url} | {response.status_code} | {response.content}"
            )
            raise HTTPException(500, messages.connection_failed)
        return response.json()
