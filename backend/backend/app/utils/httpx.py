from http import HTTPStatus
from typing import Any, Dict, Mapping

from httpx import ConnectError
from starlette.requests import Request

from backend.app.exceptions import HTTPException
from backend.app.utils import AiohttpClient
from common.constants import MESSAGE_NOT_FOUND


async def plugin_proxy_service(
        proxies: Dict[str, str],
        request: Request,
        path: str,
        data: Mapping[str, Any] = None,
        extra_params: Dict[str, Any] = None,
):
    http_client = AiohttpClient.get_aiohttp_client()
    proxy_args = {
        "url": path,
        "params": {**request.query_params, **extra_params},
        "headers": request.headers,
        "cookies": request.cookies,
        # "follow_redirects": True,
        "timeout": 60,
        "proxies": proxies,
        "data": data
    }
    try:
        if request.method == "GET":
            return await http_client.get(**proxy_args)
        if request.method == "POST":
            return await http_client.post(**proxy_args)
        if request.method == "PUT":
            return await http_client.put(**proxy_args)
        if request.method == "PATCH":
            return await http_client.patch(**proxy_args)
        if request.method == "DELETE":
            return await http_client.delete(**proxy_args)
        if request.method == "HEAD":
            return await http_client.head(**proxy_args)
        if request.method == "OPTIONS":
            return http_client.options(**proxy_args)
    except ConnectError:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, content=MESSAGE_NOT_FOUND)
