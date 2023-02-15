"""Plugin proxy controller implementation."""
import json
import logging
from typing import Any, Dict, Optional

from fastapi import Body
from starlette.requests import Request
from starlette.responses import RedirectResponse

from bettercollected_backend_server.app.utils.httpx import plugin_proxy_service
from common.enums.form_provider import FormProvider
from common.base.plugin import BasePluginRoute

log = logging.getLogger(__name__)


# noinspection PyMethodOverriding,PyProtocol
class PluginProxy(BasePluginRoute):
    proxy_url = "http://localhost:8001/api/v1/"

    async def authorize(
        self, request: Request, email: str, provider: str | FormProvider
    ):
        proxies = {f"{request.base_url}{provider}": f"{self.proxy_url}{provider}"}
        proxy = plugin_proxy_service(
            proxies, request, f"{self.proxy_url}{provider}/oauth/authorize"
        )
        authorization_url = json.loads(proxy.content)
        return RedirectResponse(authorization_url)

    async def callback(self, request: Request, provider: str | FormProvider):
        proxies = {f"{request.base_url}{provider}": f"{self.proxy_url}{provider}"}
        proxy = plugin_proxy_service(
            proxies, request, f"{self.proxy_url}{provider}/oauth/callback"
        )
        json_credentials, client_referer_url = json.loads(proxy.content)
        if client_referer_url is not None:
            return RedirectResponse(client_referer_url)
        return json.loads(json_credentials)

    async def revoke(self, request: Request, email: str, provider: str | FormProvider):
        proxies = {f"{request.base_url}{provider}": f"{self.proxy_url}{provider}"}
        proxy = plugin_proxy_service(
            proxies, request, f"{self.proxy_url}{provider}/oauth/revoke"
        )
        return proxy.content

    async def list_forms(
        self, request: Request, email: str, provider: str | FormProvider
    ):
        proxies = {f"{request.base_url}{provider}": f"{self.proxy_url}{provider}"}
        proxy = plugin_proxy_service(
            proxies, request, f"{self.proxy_url}{provider}/forms"
        )
        return json.loads(proxy.content)

    async def get_form(
        self, request: Request, form_id: str, email: str, provider: str | FormProvider
    ):
        proxies = {f"{request.base_url}{provider}": f"{self.proxy_url}{provider}"}
        proxy = plugin_proxy_service(
            proxies, request, f"{self.proxy_url}{provider}/forms/{form_id}"
        )
        return json.loads(proxy.content)

    async def import_form(
        self,
        request: Request,
        form_id: str,
        email: str,
        provider: str | FormProvider,
        data_owner_field: Optional[str] = None,
    ):
        proxies = {f"{request.base_url}{provider}": f"{self.proxy_url}{provider}"}
        proxy = plugin_proxy_service(
            proxies, request, f"{self.proxy_url}{provider}/forms/{form_id}/import"
        )
        return json.loads(proxy.content)

    async def create_form(
        self,
        request: Request,
        email: str,
        provider: str | FormProvider,
        request_body: Dict[str, Any] = Body(...),
    ):
        pass

    async def update_form(
        self,
        request: Request,
        form_id: str,
        email: str,
        provider: str | FormProvider,
        request_body: Dict[str, Any] = Body(...),
    ):
        pass

    async def delete_form(
        self, request: Request, form_id: str, email: str, provider: str | FormProvider
    ):
        pass

    async def list_form_responses(
        self, request: Request, form_id: str, email: str, provider: str | FormProvider
    ):
        pass

    async def get_form_response(
        self,
        request: Request,
        form_id: str,
        email: str,
        response_id: str,
        provider: str | FormProvider,
    ):
        pass

    async def delete_form_response(
        self,
        request: Request,
        form_id: str,
        email: str,
        response_id: str,
        provider: str | FormProvider,
    ):
        pass
