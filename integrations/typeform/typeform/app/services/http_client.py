import logging
import typing

import aiohttp
from httpx import AsyncClient

from typeform.app.constants import messages
from typeform.app.exceptions import HTTPException

log = logging.getLogger(__name__)


class HttpClient(AsyncClient):

    async def get(self, *args, **kwargs) -> typing.Any:
        response = await super().get(*args, **kwargs)
        return response.json()
