"""Plugin proxy controller implementation."""
import logging
from typing import Any, Dict, Optional

from fastapi import Body
from starlette.requests import Request

from common.enums.form_provider import FormProvider
from common.base.plugin import BasePluginRoute

log = logging.getLogger(__name__)


class PluginProxy(BasePluginRoute):
    async def authorize(
        self, request: Request, email: str, provider: str | FormProvider
    ):
        pass

    async def callback(self, request: Request, provider: str | FormProvider):
        pass

    async def revoke(self, email: str, provider: str | FormProvider):
        pass

    async def list_forms(self, email: str, provider: str | FormProvider):
        pass

    async def get_form(self, form_id: str, email: str, provider: str | FormProvider):
        pass

    async def import_form(
        self,
        form_id: str,
        email: str,
        provider: str | FormProvider,
        data_owner_field: Optional[str] = None,
    ):
        pass

    async def create_form(
        self,
        email: str,
        provider: str | FormProvider,
        request_body: Dict[str, Any] = Body(...),
    ):
        pass

    async def update_form(
        self,
        form_id: str,
        email: str,
        provider: str | FormProvider,
        request_body: Dict[str, Any] = Body(...),
    ):
        pass

    async def delete_form(self, form_id: str, email: str, provider: str | FormProvider):
        pass

    async def list_form_responses(
        self, form_id: str, email: str, provider: str | FormProvider
    ):
        pass

    async def get_form_response(
        self, form_id: str, email: str, response_id: str, provider: str | FormProvider
    ):
        pass

    async def delete_form_response(
        self, form_id: str, email: str, response_id: str, provider: str | FormProvider
    ):
        pass
