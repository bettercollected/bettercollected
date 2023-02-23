from beanie import PydanticObjectId
from starlette.requests import Request

from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.schemas.standard_form_response import FormResponseDocument
from backend.app.services.form_plugin_provider_service import FormPluginProviderService
from backend.app.services.form_service import FormService
from backend.app.services.plugin_proxy_service import PluginProxyService
from backend.app.services.workspace_user_service import WorkspaceUserService
from backend.app.utils import AiohttpClient
from common.enums.http_methods import HTTPMethods
from common.models.form_import import FormImportRequestBody, FormImportResponse
from common.models.standard_form import StandardFormDto
from common.models.user import User


class WorkspaceFormService:

    def __init__(self,
                 form_provider_service: FormPluginProviderService,
                 plugin_proxy_service: PluginProxyService,
                 workspace_user_service: WorkspaceUserService,
                 form_service: FormService,
                 workspace_form_repository: WorkspaceFormRepository
                 ):
        self.form_provider_service = form_provider_service
        self.plugin_proxy_service = plugin_proxy_service
        self.workspace_user_service = workspace_user_service
        self.form_service = form_service
        self.workspace_form_repository = workspace_form_repository

    # TODO : Use plugin interface for importing for now endpoint is used here
    async def import_form_to_workspace(self,
                                       workspace_id: PydanticObjectId,
                                       provider: str,
                                       form_import: FormImportRequestBody,
                                       user: User,
                                       request: Request):
        await self.workspace_user_service.check_user_is_admin_in_workspace(workspace_id, user)
        provider_url = await self.form_provider_service.get_provider_url(provider)
        response = await AiohttpClient.get_aiohttp_client().get(
            url=f"{provider_url}/{provider}/forms/convert/standard_form",
            json=form_import.dict(),
            cookies=request.cookies,
            timeout=60
        )
        response_data = await response.json()
        form_data = FormImportResponse.parse_obj(response_data)
        standard_form = form_data.form
        await self.form_service.save_form(standard_form)
        await self.workspace_form_repository.save_workspace_form(
            workspace_id=workspace_id,
            form_id=standard_form.formId,
            user_id=user.id,
            workspace_form_settings=WorkspaceFormSettings(
                custom_url=standard_form.formId,
                response_data_owner_field=form_import.response_data_owner,
                # TODO : Refactor repeated information provider is only saved on form
                #  as it doesn't change with workspaces
                provider=standard_form.settings.provider,
                private=standard_form.settings.private
            ))
        responses = form_data.responses
        # TODO : Make this scalable in case of large number of responses
        for response in responses:
            existing_response = await FormResponseDocument.find_one({'responseId': response.responseId})
            response_document = FormResponseDocument(**response.dict())
            if existing_response:
                response_document.id = existing_response.id
            response_document.formId = standard_form.formId
            # TODO : Handle data owner identifier in workspace
            data_owner_answer = response_document.responses.get(
                form_import.response_data_owner)
            response_document.dataOwnerIdentifier = data_owner_answer.answer if data_owner_answer else None
            await response_document.save()
