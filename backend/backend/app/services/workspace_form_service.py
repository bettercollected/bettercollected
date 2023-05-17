from http import HTTPStatus

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from beanie import PydanticObjectId
from starlette.requests import Request

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.schedulers.form_schedular import FormSchedular
from backend.app.services.form_import_service import FormImportService
from backend.app.services.form_plugin_provider_service import FormPluginProviderService
from backend.app.services.form_response_service import FormResponseService
from backend.app.services.form_service import FormService
from backend.app.services.plugin_proxy_service import PluginProxyService
from backend.app.services.responder_groups_service import ResponderGroupsService
from backend.app.services.workspace_user_service import WorkspaceUserService
from backend.app.utils import AiohttpClient
from backend.config import settings
from common.enums.plan import Plans
from common.models.form_import import FormImportRequestBody
from common.models.user import User


class WorkspaceFormService:
    def __init__(
        self,
        form_provider_service: FormPluginProviderService,
        plugin_proxy_service: PluginProxyService,
        workspace_user_service: WorkspaceUserService,
        form_service: FormService,
        workspace_form_repository: WorkspaceFormRepository,
        form_schedular: FormSchedular,
        form_import_service: FormImportService,
        schedular: AsyncIOScheduler,
        form_response_service: FormResponseService,
        responder_groups_service: ResponderGroupsService = container.responder_groups_service(),
    ):
        self.form_provider_service = form_provider_service
        self.plugin_proxy_service = plugin_proxy_service
        self.workspace_user_service = workspace_user_service
        self.form_service = form_service
        self.workspace_form_repository = workspace_form_repository
        self.form_schedular = form_schedular
        self.form_import_service = form_import_service
        self.schedular = schedular
        self.form_response_service = form_response_service
        self.responder_groups_service = responder_groups_service

    # TODO : Use plugin interface for importing for now endpoint is used here
    async def import_form_to_workspace(
        self,
        workspace_id: PydanticObjectId,
        provider: str,
        form_import: FormImportRequestBody,
        user: User,
        request: Request,
    ):
        await self.workspace_user_service.check_user_has_access_in_workspace(
            workspace_id, user
        )

        await self.workspace_form_repository.check_is_form_imported_in_other_workspace(
            workspace_id=workspace_id, form_id=form_import.form.get("formId")
        )

        can_import_form = await self.check_if_user_can_import_more_forms(
            user=user, workspace_id=workspace_id
        )
        if not can_import_form:
            raise HTTPException(
                status_code=403, content="Upgrade plan to import more forms"
            )
        response_data = await self.convert_form(
            provider=provider, request=request, form_import=form_import
        )
        standard_form = (
            await self.form_import_service.save_converted_form_and_responses(
                response_data, form_import.response_data_owner
            )
        )
        if not standard_form:
            raise HTTPException(
                HTTPStatus.INTERNAL_SERVER_ERROR, content="Failed to import form"
            )
        embed_url = (
            standard_form.settings.embed_url
            if standard_form.settings and standard_form.settings.embed_url
            else ""
        )
        await self.workspace_form_repository.save_workspace_form(
            workspace_id=workspace_id,
            form_id=standard_form.form_id,
            user_id=user.id,
            workspace_form_settings=WorkspaceFormSettings(
                custom_url=standard_form.form_id,
                embed_url=embed_url,
                response_data_owner_field=form_import.response_data_owner,
                # TODO : Refactor repeated information provider is only saved on form
                #  as it doesn't change with workspaces
                provider=standard_form.settings.provider,
                private=not standard_form.settings.is_public,
            ),
        )
        self.schedular.add_job(
            self.form_schedular.update_form,
            "interval",
            id=f"{provider}_{standard_form.form_id}",
            coalesce=True,
            replace_existing=True,
            kwargs={
                "user": user,
                "provider": provider,
                "form_id": standard_form.form_id,
                "response_data_owner": form_import.response_data_owner,
            },
            minutes=settings.schedular_settings.INTERVAL_MINUTES,
        )

    async def convert_form(self, *, provider, request, form_import):
        provider_url = await self.form_provider_service.get_provider_url(provider)
        response = await AiohttpClient.get_aiohttp_client().post(
            url=f"{provider_url}/{provider}/forms/convert/standard_form",
            json=form_import.form,
            cookies=request.cookies,
            timeout=60,
        )
        response_data = await response.json()
        return response_data

    async def check_if_user_can_import_more_forms(
        self, user: User, workspace_id: PydanticObjectId
    ):
        if user.plan == Plans.PRO:
            return True

        workspace_forms = await self.get_form_ids_in_workspace(
            workspace_id=workspace_id
        )

        if len(workspace_forms) >= 10:
            return False
        return True

    async def delete_form_from_workspace(
        self, workspace_id: PydanticObjectId, form_id: str, user: User
    ):
        await self.workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        workspace_ids = (
            await self.workspace_form_repository.get_workspace_ids_for_form_id(form_id)
        )
        workspace_form = await self.workspace_form_repository.delete_form_in_workspace(
            workspace_id=workspace_id, form_id=form_id
        )
        if len(workspace_ids) > 1:
            return "Form deleted form workspace."
        self.schedular.remove_job(f"{workspace_form.settings.provider}_{form_id}")
        await self.form_service.delete_form(form_id=form_id)
        await self.form_response_service.delete_form_responses(form_id=form_id)
        await self.form_response_service.delete_deletion_requests(form_id=form_id)
        return "Form deleted form workspace."

    async def get_form_ids_in_workspace(self, workspace_id: PydanticObjectId):
        return await self.workspace_form_repository.get_form_ids_in_workspace(
            workspace_id
        )

    async def get_form_ids_imported_by_user(
        self, workspace_id: PydanticObjectId, user_id: PydanticObjectId
    ):
        return await self.workspace_form_repository.get_form_ids_imported_by_user(
            workspace_id, str(user_id)
        )

    async def add_group_to_form(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        group_id: PydanticObjectId,
        user: User,
    ):
        await self.workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        return await self.responder_groups_service.add_group_to_form(
            form_id=form_id, group_id=group_id
        )

    async def delete_group_from_form(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        group_id: PydanticObjectId,
        user: User,
    ):
        await self.workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        return await self.responder_groups_service.remove_group_from_form(
            form_id=form_id, group_id=group_id
        )
