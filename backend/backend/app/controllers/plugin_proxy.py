"""Plugin proxy controller implementation."""
import json
import logging
from typing import Any, Dict, Optional

from fastapi import Body
from starlette.requests import Request

from backend.app.container import container
from backend.app.core.form_plugin_config import FormProvidersConfig
from backend.app.services.plugin_proxy_service import PluginProxyService
from common.base.plugin import BasePluginRoute
from common.enums.form_provider import FormProvider

log = logging.getLogger(__name__)


class PluginProxy(BasePluginRoute):

    def __init__(self,
                 plugin_proxy_service: PluginProxyService
                 = container.plugin_proxy_service(),
                 form_providers: FormProvidersConfig
                 = container.form_providers()
                 ):
        self.plugin_proxy_service = plugin_proxy_service
        self.form_providers = form_providers

    async def list_forms(
            self,
            provider: str | FormProvider,
            request: Request,
    ):
        proxy_url = self.form_providers.get_form_provider(provider).provider_url
        data = await self.plugin_proxy_service.pass_request(
            request,
            f"{proxy_url}/{provider}/forms"
        )
        return data

    async def get_form(
            self, form_id: str, email: str, provider: str | FormProvider, request: Request
    ):
        proxy_url = self.form_providers.get_form_provider(provider).provider_url
        data = await self.plugin_proxy_service.pass_request(
            request, f"{proxy_url}/{provider}/forms/{form_id}"
        )
        return data

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
        proxies = {f"{request.base_url}{provider}": f"{self.proxy_url}{provider}"}
        proxy = plugin_proxy_service(
            proxies, request, f"{self.proxy_url}{provider}/forms", data=request_body
        )
        return json.loads(proxy.content)

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
