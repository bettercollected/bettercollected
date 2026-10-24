import logging
from http import HTTPStatus
from typing import Any, Mapping, Dict
from urllib.parse import urlparse

from httpx import ConnectError
from starlette.requests import Request

from backend.app.constants import messages
from backend.app.exceptions import HTTPException
from common.constants import MESSAGE_NOT_FOUND
from common.enums.http_methods import HTTPMethods
from common.services.http_client import HttpClient

log = logging.getLogger(__name__)


def _upstream_error(response) -> Any:
    """The upstream service's own error body (JSON), or None when it has none."""
    try:
        return response.json()
    except ValueError:
        return None


def _error_code(content: Any) -> str:
    """A short error code from an upstream error body, for the log: never the
    body itself (it may carry user input)."""
    if isinstance(content, dict):
        for key in ("error", "code", "status"):
            value = content.get(key)
            if isinstance(value, (str, int)) and len(str(value)) <= 64:
                return str(value)
    return "-"


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
            headers, cookies = request.headers, request.cookies
            fresh_access_token = getattr(request.state, "access_token", None)
            if fresh_access_token:
                # the session was refreshed for this request: forward the new
                # access token, not the expired one (the Cookie header would
                # win over ``cookies``, so it is rebuilt from them)
                headers = {
                    k: v for k, v in request.headers.items() if k.lower() != "cookie"
                }
                cookies = {**request.cookies, "Authorization": fresh_access_token}
            response = await self.http_client.request(
                method=method if method else request.method,
                url=url,
                json=data,
                params=query_params,
                headers=headers,
                cookies=cookies,
                timeout=60,
            )

            if response.status_code != HTTPStatus.OK:
                content = _upstream_error(response)
                log.warning(
                    "plugin request to %s failed: upstream status %s, error %s",
                    urlparse(url).path,
                    response.status_code,
                    _error_code(content),
                )
                if 400 <= response.status_code < 600:
                    # the plugin's own status and message (an expired or
                    # refused authorization, a missing scope, ...), not a
                    # generic one that hides the cause
                    raise HTTPException(
                        status_code=response.status_code,
                        content=(
                            content
                            if content is not None
                            else messages.proxy_server_error
                        ),
                    )
                raise HTTPException(
                    HTTPStatus.INTERNAL_SERVER_ERROR, messages.proxy_server_error
                )
            return response.json()
        except ConnectError:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content=MESSAGE_NOT_FOUND
            )
