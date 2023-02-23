"""Plugin proxy controller implementation."""
import json
import logging
from http import HTTPStatus
from typing import Any, Dict, Optional

from fastapi import Body, Depends
from starlette.requests import Request

from backend.app.container import container
from backend.app.services.form_plugin_provider_service import FormPluginProviderService
from backend.app.services.plugin_proxy_service import PluginProxyService
from backend.app.services.user_service import get_logged_user
from common.base.plugin import BasePluginRoute
from common.enums.form_provider import FormProvider
from common.exceptions.http import HTTPException
from common.models.user import User

log = logging.getLogger(__name__)


# noinspection PyMethodOverriding,PyProtocol
class PluginProxy(BasePluginRoute):
    def __init__(
            self,
            plugin_proxy_service: PluginProxyService = container.plugin_proxy_service(),
            form_provider_service: FormPluginProviderService = container.form_provider_service(),
    ):
        self.plugin_proxy_service = plugin_proxy_service
        self.form_provider_service = form_provider_service

    async def list_forms(
            self,
            provider: str | FormProvider,
            request: Request,
            user: User = Depends(get_logged_user),
    ):
        proxy_url = (
            await self.form_provider_service.get_provider(provider, True)
        ).provider_url
        data = await self.plugin_proxy_service.pass_request(
            request, f"{proxy_url}/{provider}/forms"
        )
        return data

    async def get_form(
            self,
            form_id: str,
            email: str,
            provider: str | FormProvider,
            request: Request,
            user: User = Depends(get_logged_user),
    ):
        proxy_url = (
            await self.form_provider_service.get_provider(provider, True)
        ).provider_url
        data = await self.plugin_proxy_service.pass_request(
            request, f"{proxy_url}/{provider}/forms/{form_id}"
        )
        return data

    async def import_form(
            self,
            form_id: str,
            provider: str | FormProvider,
            request: Request,
    ):
        proxy_url = (
            await self.form_provider_service.get_provider(provider, True)
        ).provider_url
        data = await self.plugin_proxy_service.pass_request(
            request, f"{proxy_url}/{provider}/forms/{form_id}"
        )
        return data

    async def import_forms(
            self,
            provider: str | FormProvider,
            request: Request
    ):
        proxy_url = (
            await self.form_provider_service.get_provider(provider, True)
        ).provider_url
        data = await self.plugin_proxy_service.pass_request(
            request, f"{proxy_url}/{provider}/forms"
        )
        return data

    async def create_form(
            self,
            request: Request,
            email: str,
            provider: str | FormProvider,
            request_body: Dict[str, Any] = Body(...),
            user: User = Depends(get_logged_user),
    ):
        proxy_url = (
            await self.form_provider_service.get_provider(provider, True)
        ).provider_url
        data = await self.plugin_proxy_service.pass_request(
            request, f"{proxy_url}/{provider}/forms", data=request_body
        )
        return data

    async def update_form(
            self,
            request: Request,
            form_id: str,
            email: str,
            provider: str | FormProvider,
            request_body: Dict[str, Any] = Body(...),
            user: User = Depends(get_logged_user),
    ):
        raise HTTPException(status_code=HTTPStatus.NOT_IMPLEMENTED)

    async def delete_form(
            self,
            request: Request,
            form_id: str,
            email: str,
            provider: str | FormProvider,
            user: User = Depends(get_logged_user),
    ):
        raise HTTPException(status_code=HTTPStatus.NOT_IMPLEMENTED)

    async def list_form_responses(
            self,
            request: Request,
            form_id: str,
            email: str,
            provider: str | FormProvider,
            user: User = Depends(get_logged_user),
    ):
        raise HTTPException(status_code=HTTPStatus.NOT_IMPLEMENTED)

    async def get_form_response(
            self,
            request: Request,
            form_id: str,
            email: str,
            response_id: str,
            provider: str | FormProvider,
            user: User = Depends(get_logged_user),
    ):
        raise HTTPException(status_code=HTTPStatus.NOT_IMPLEMENTED)

    async def delete_form_response(
            self,
            request: Request,
            form_id: str,
            email: str,
            response_id: str,
            provider: str | FormProvider,
            user: User = Depends(get_logged_user),
    ):
        raise HTTPException(status_code=HTTPStatus.NOT_IMPLEMENTED)
