from http import HTTPStatus
from typing import Any, Mapping, Dict

from httpx import ConnectError
from starlette.requests import Request

from backend.app.constants import messages
from backend.app.exceptions import HTTPException
from common.constants import MESSAGE_NOT_FOUND
from common.enums.http_methods import HTTPMethods
from common.services.http_client import HttpClient


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
        extra_params: Dict[str, str] = None,
    ) -> Mapping[str, Any]:
        # Merge query params if params is not none
        try:
            query_params = dict(request.query_params)
            if extra_params:
                query_params.update(extra_params)
            response = await self.http_client.request(
                method=method if method else request.method,
                url=url,
                json=data,
                params=query_params,
                headers=request.headers,
                cookies=request.cookies,
                timeout=60,
            )

            if response.status_code == HTTPStatus.NOT_FOUND:
                raise HTTPException(
                    status_code=HTTPStatus.NOT_FOUND, content=response.json()
                )
            if response.status_code == HTTPStatus.UNAUTHORIZED:
                raise HTTPException(
                    status_code=HTTPStatus.UNAUTHORIZED, content=response.json()
                )
            if response.status_code == HTTPStatus.FORBIDDEN:
                raise HTTPException(
                    status_code=HTTPStatus.FORBIDDEN, content=response.json()
                )
            if response.status_code != HTTPStatus.OK:
                raise HTTPException(
                    HTTPStatus.INTERNAL_SERVER_ERROR, messages.proxy_server_error
                )
            return response.json()
        except ConnectError:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content=MESSAGE_NOT_FOUND
            )
