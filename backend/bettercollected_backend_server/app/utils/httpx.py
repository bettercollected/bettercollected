from typing import Dict

import httpx
from starlette.requests import Request


def plugin_proxy_service(proxies: Dict[str, str], request: Request, path: str):
    proxy_args = {
        "url": path,
        "params": request.query_params,
        "headers": request.headers,
        "cookies": request.cookies,
        # "follow_redirects": True,
        "timeout": 60,
        "proxies": proxies,
    }
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
