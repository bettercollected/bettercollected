"""Plugin proxy controller implementation."""
import json
import logging
from typing import Any, Dict, Optional

import jwt
from fastapi import Body, Depends
from starlette.requests import Request
from starlette.responses import RedirectResponse

from backend.app.container import container
from backend.app.services.auth_proxy_service import AuthProxyService
from backend.app.services.user_service import get_logged_user
from backend.app.utils.httpx import plugin_proxy_service
from backend.config import settings
from common.enums.form_provider import FormProvider
from common.base.plugin import BasePluginRoute
from common.models.user import User

log = logging.getLogger(__name__)


# noinspection PyMethodOverriding,PyProtocol
class PluginProxy(BasePluginRoute):
    # TODO : Refactor proxy url to get from the config file
    proxy_url = settings.provider_plugin.GOOGLE_SERVICE

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
            self,
            provider: str | FormProvider,
            request: Request,
            user: User = Depends(get_logged_user)
    ):
        # TODO : Inject auth services
        proxy_url = container.enabled_forms().get_form_provider(provider).provider_url
        credential = await AuthProxyService().get_credential_of_provider(provider, request.cookies['Authorization'])
        jwt_token = jwt.encode(credential, key=settings.JWT_SECRET)
        proxies = {f"{request.base_url}{provider}": f"{proxy_url}{provider}"}
        proxy = await plugin_proxy_service(
            proxies, request, f"{proxy_url}{provider}/forms",
            extra_params={"jwt_token": jwt_token}
        )
        return json.loads(proxy.content)

    async def get_form(
            self, request: Request, form_id: str, email: str, provider: str | FormProvider
    ):
        proxy_url = container.enabled_forms().get_form_provider(provider).provider_url
        proxies = {f"{request.base_url}{provider}": f"{proxy_url}{provider}"}
        proxy = await plugin_proxy_service(
            proxies, request, f"{proxy_url}{provider}/forms/{form_id}"
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
