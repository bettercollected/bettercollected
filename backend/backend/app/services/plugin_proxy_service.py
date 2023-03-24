import logging
from http import HTTPStatus
from typing import Any, Mapping

from backend.app.constants import messages
from backend.app.exceptions import HTTPException

from common.constants import MESSAGE_NOT_FOUND
from common.enums.http_methods import HTTPMethods
from common.services.http_client import HttpClient

from httpx import ConnectError

from starlette.requests import Request


class PluginProxyService:
    def __init__(self, http_client: HttpClient):
        self.http_client = http_client

    async def pass_request(
        self,
        request: Request,
        url: str,
        *,
        method: HTTPMethods = None,
        data: Mapping[str, Any] = None,
    ) -> Mapping[str, Any]:
        # Merge query params if params is not none
        try:
            response = await self.http_client.request(
                method=method if method else request.method,
                url=url,
                json=data,
                params=request.query_params,
                headers=request.headers,
                cookies=request.cookies,
                timeout=60,
            )
            if response.status_code != HTTPStatus.OK:
                logging.error(response.url)
                logging.error(response.status_code)
                logging.error(response.content)
                raise HTTPException(
                    HTTPStatus.INTERNAL_SERVER_ERROR, messages.proxy_server_error
                )
            return response.json()
        except ConnectError:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content=MESSAGE_NOT_FOUND
            )
