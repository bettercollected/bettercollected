from http import HTTPStatus
from typing import Any, Dict, Mapping

import httpx
from httpx import ConnectError
from starlette.requests import Request

from bettercollected_backend_server.app.exceptions import HTTPException
from common.constants import MESSAGE_NOT_FOUND


def plugin_proxy_service(
    proxies: Dict[str, str], request: Request, path: str, data: Mapping[str, Any] = None
):
    proxy_args = {
        "url": path,
        "params": request.query_params,
        "headers": request.headers,
        "cookies": request.cookies,
        # "follow_redirects": True,
        "timeout": 60,
        "proxies": proxies,
    }
    # if data:
    #     proxy_args["data"] = data
    try:
        if request.method == "GET":
            return httpx.get(**proxy_args)
        if request.method == "POST":
            return httpx.post(**proxy_args)
        if request.method == "PUT":
            return httpx.put(**proxy_args)
        if request.method == "PATCH":
            return httpx.patch(**proxy_args)
        if request.method == "DELETE":
            return httpx.delete(**proxy_args)
        if request.method == "HEAD":
            return httpx.head(**proxy_args)
        if request.method == "OPTIONS":
            return httpx.options(**proxy_args)
    except ConnectError:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, content=MESSAGE_NOT_FOUND)
