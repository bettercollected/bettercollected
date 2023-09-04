import logging
import typing
from http import HTTPStatus

from common.constants import messages
from common.exceptions.http import HTTPException

from httpx import AsyncClient, ConnectError

log = logging.getLogger(__name__)


class HttpClient(AsyncClient):
    async def get(self, *args, **kwargs) -> typing.Mapping[str, typing.Any]:
        try:
            response = await super().get(*args, **kwargs)
            if response.status_code != 200:
                logging.error(
                    f"Response status: {response.url} | {response.status_code} | {response.content}"
                )
                raise HTTPException(500, messages.connection_failed)
            return response.json()
        except ConnectError:
            raise HTTPException(status_code=HTTPStatus.SERVICE_UNAVAILABLE, content='Requested Source not available.')

    async def post(self, *args, **kwargs) -> typing.Mapping[str, typing.Any]:
        try:
            response = await super().post(*args, **kwargs)
            if response.status_code != 200:
                logging.error(
                    f"Response status: {response.url} | {response.status_code} | {response.content}"
                )
                raise HTTPException(500, messages.connection_failed)
            return response.json()
        except ConnectError:
            raise HTTPException(status_code=HTTPStatus.SERVICE_UNAVAILABLE, content='Requested Source not available.')
