from http import HTTPStatus
from typing import Any, Dict

from beanie import PydanticObjectId
from loguru import logger

from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.app.services.form_import_service import FormImportService
from backend.app.services.form_plugin_provider_service import FormPluginProviderService
from backend.app.utils import AiohttpClient
from backend.config import settings
from common.models.user import User
from common.services.jwt_service import JwtService


class FormSchedular:
    def __init__(
        self,
        form_provider_service: FormPluginProviderService,
        form_import_service: FormImportService,
        jwt_service: JwtService,
    ):
        self.form_provider_service = form_provider_service
        self.form_import_service = form_import_service
        self.jwt_service = jwt_service

    async def update_form(
        self,
        *,
        form_id,
        workspace_id: PydanticObjectId = None,
    ):
        logger.info(f"Job started for form {form_id} by schedular.")
        workspace_form = await WorkspaceFormDocument.find_one(
            {"form_id": form_id, "workspace_id": workspace_id}
        )
        users_response = await self.fetch_user_details([workspace_form.user_id])
        standard_form = None
        if users_response:
            user_response = (
                users_response.get("users_info")[0]
                if len(users_response.get("users_info")) > 0
                else None
            )
            if not user_response:
                logger.info(
                    ("Schedular for form " + form_id + ": Could not fetch user details")
                )
                logger.error(
                    f"Error while updating form with id {form_id} by schedular"
                )
                return

            user = User(
                **user_response,
                id=user_response.get("_id"),
                sub=user_response.get("email"),
            )

            cookies = {"Authorization": self.jwt_service.encode(user)}

            # TODO Make it do with proxy service after service and proxy router refactored
            raw_form = await self.perform_request(
                provider=workspace_form.settings.provider,
                append_url=f"/{form_id}",
                method="GET",
                cookies=cookies,
            )

            if not raw_form:
                logger.error("Could not fetch form form provider")
            # if the latest status of form is not closed then perform saving
            if raw_form:
                response_data = await self.perform_conversion_request(
                    provider=workspace_form.settings.provider,
                    raw_form=raw_form,
                    cookies=cookies,
                )
                if response_data:
                    standard_form = await self.form_import_service.save_converted_form_and_responses(
                        response_data,
                        workspace_form.settings.response_data_owner_field,
                        workspace_id=workspace_id,
                    )
        if standard_form:
            logger.info(f"Form {form_id} is updated successfully by schedular.")
        else:
            logger.error(f"Error while updating form with id {form_id} by schedular")

    async def perform_conversion_request(
        self,
        *,
        provider: str,
        raw_form: Dict[str, Any],
        convert_responses: bool = True,
        cookies: Dict = None,
    ):
        return await self.perform_request(
            provider=provider,
            append_url="/convert/standard_form",
            method="POST",
            cookies=cookies,
            json=raw_form,
            params={"convert_responses": str(convert_responses)},
        )

    async def perform_request(
        self,
        *,
        provider: str,
        append_url: str,
        method: str,
        cookies: Dict,
        params: Dict = None,
        json: Dict = None,
    ):
        provider_url = await self.form_provider_service.get_provider_url(provider)
        # TODO Perform request from containers http client
        response = await AiohttpClient.get_aiohttp_client().request(
            method=method,
            url=f"{provider_url}/{provider}/forms{append_url}",
            params=params,
            cookies=cookies,
            json=json,
            timeout=60,
        )
        if response.status != HTTPStatus.OK:
            logger.error(await response.json())
            return None
        data = await response.json()
        return data

    async def fetch_user_details(self, user_ids):
        response = await AiohttpClient.get_aiohttp_client().get(
            f"{settings.auth_settings.BASE_URL}/users",
            params={"user_ids": user_ids},
        )
        return await response.json()
