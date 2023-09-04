import os
from http import HTTPStatus
from typing import List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from beanie import PydanticObjectId
from fastapi import UploadFile
from starlette.requests import Request

from backend.app.exceptions import HTTPException
from backend.app.models.response_dtos import FormFileResponse
from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.schedulers.form_schedular import FormSchedular
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.standard_form_response import (
    FormResponseDocument,
    FormResponseDeletionRequest,
)
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.app.services.aws_service import AWSS3Service
from backend.app.services.form_import_service import FormImportService
from backend.app.services.form_plugin_provider_service import FormPluginProviderService
from backend.app.services.form_response_service import FormResponseService
from backend.app.services.form_service import FormService
from backend.app.services.plugin_proxy_service import PluginProxyService
from backend.app.services.responder_groups_service import ResponderGroupsService
from backend.app.services.temporal_service import TemporalService
from backend.app.services.user_tags_service import UserTagsService
from backend.app.services.workspace_user_service import WorkspaceUserService
from backend.app.utils import AiohttpClient
from common.enums.plan import Plans
from common.models.form_import import FormImportRequestBody
from common.models.standard_form import StandardForm, StandardFormResponse
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
        responder_groups_service: ResponderGroupsService,
        user_tags_service: UserTagsService,
        temporal_service: TemporalService,
        aws_service: AWSS3Service,
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
        self.user_tags_service = user_tags_service
        self.temporal_service = temporal_service
        self._aws_service = aws_service

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
                response_data,
                form_import.response_data_owner,
                workspace_id=workspace_id,
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
        await self.temporal_service.add_scheduled_job_for_importing_form(
            workspace_id=workspace_id, form_id=standard_form.form_id
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

        if len(workspace_forms) >= 100:
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
            return "Form deleted from workspace."
        if workspace_form.settings.provider != "self":
            await self.temporal_service.delete_form_import_schedule(
                workspace_id, form_id
            )

        await self.form_service.delete_form(form_id=form_id)
        await self.form_response_service.delete_form_responses(form_id=form_id)
        await self.form_response_service.delete_deletion_requests(form_id=form_id)
        await self.responder_groups_service.responder_groups_repo.delete_workspace_form_groups(
            form_id=form_id
        )
        return "Form deleted from workspace."

    async def get_form_ids_in_workspace(self, workspace_id: PydanticObjectId):
        return await self.workspace_form_repository.get_form_ids_in_workspace(
            workspace_id
        )

    async def get_form_ids_in_workspaces_and_imported_by_user(
        self, workspace_ids: List[PydanticObjectId], user: User
    ):
        return await self.workspace_form_repository.get_form_ids_in_workspaces_and_imported_by_user(
            workspace_ids=workspace_ids, user=user
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
        await self.responder_groups_service.remove_group_from_form(
            form_id=form_id, group_id=group_id
        )

    async def delete_forms_with_ids(self, form_ids: List[str]):
        workspace_forms = (
            await self.workspace_form_repository.get_workspace_forms_form_ids(
                form_ids=form_ids
            )
        )
        for workspace_form in workspace_forms:
            if workspace_form.settings.provider != "self":
                await self.temporal_service.delete_form_import_schedule(
                    workspace_form.workspace_id, workspace_form.form_id
                )
        await self.form_response_service.delete_form_responses_of_form_ids(
            form_ids=form_ids
        )
        await self.form_response_service.delete_deletion_requests_of_form_ids(
            form_ids=form_ids
        )
        await self.form_service.delete_forms(form_ids=form_ids)
        return await self.workspace_form_repository.delete_forms(form_ids=form_ids)

    async def generate_presigned_file_url(
        self,
        key: str,
    ):
        # await self.workspace_user_service.check_is_admin_in_workspace(
        #     workspace_id=workspace_id, user=user
        # )
        #
        # response = await FormResponseDocument.find_one({"response_id": response_id})
        # form = await FormDocument.find_one({"form_id": form_id})
        # workspace_form = await WorkspaceFormDocument.find_one(
        #     {
        #         "workspace_id": workspace_id,
        #         "form_id": form.form_id,
        #     }
        # )
        #
        # if not workspace_form:
        #     raise HTTPException(404, "Form not found in this workspace")
        #
        # if not response:
        #     raise HTTPException(404, "Response not found in this workspace")
        #
        # if not response.dataOwnerIdentifier == user.sub:
        #     raise HTTPException(403, "You are not authorized to perform this action.")

        return self._aws_service.generate_presigned_url(key)

    async def create_form(
        self,
        workspace_id: PydanticObjectId,
        form: StandardForm,
        user: User,
        logo: UploadFile = None,
        cover_image: UploadFile = None,
    ):
        await self.workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        form.form_id = str(PydanticObjectId())

        if logo:
            logo_url = await self._aws_service.upload_file_to_s3(
                file=logo.file,
                key=form.form_id + f"_logo{os.path.splitext(logo.filename)[1]}",
            )
            form.logo = logo_url
        if cover_image:
            cover_image_url = await self._aws_service.upload_file_to_s3(
                file=cover_image.file,
                key=form.form_id + f"_cover{os.path.splitext(cover_image.filename)[1]}",
            )
            form.cover_image = cover_image_url

        saved_form = await self.form_service.create_form(form=form)
        workspace_form_settings = WorkspaceFormSettings(
            custom_url=form.form_id,
            provider="self",
            privacy_policy_url=form.settings.privacy_policy_url
            if form.settings
            else "",
            response_data_owner_field=form.settings.response_data_owner_field
            if form.settings
            else "",
        )
        await self.workspace_form_repository.save_workspace_form(
            workspace_id=workspace_id,
            form_id=form.form_id,
            user_id=user.id,
            workspace_form_settings=workspace_form_settings,
        )
        saved_form.settings = workspace_form_settings
        return saved_form

    async def update_form(
        self,
        workspace_id: PydanticObjectId,
        form_id: PydanticObjectId,
        form: StandardForm,
        user: User,
        logo: UploadFile = None,
        cover_image: UploadFile = None,
    ):
        await self.workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        workspace_forms = (
            await self.workspace_form_repository.get_workspace_forms_form_ids(
                [str(form_id)]
            )
        )
        if (len(workspace_forms)) == 0:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="Form not found in workspace"
            )
        workspace_form = workspace_forms[0]
        if form.settings:
            if form.settings.response_data_owner_field is not None:
                workspace_form.settings.response_data_owner_field = (
                    form.settings.response_data_owner_field
                )
            if form.settings.privacy_policy_url is not None:
                workspace_form.settings.privacy_policy_url = (
                    form.settings.privacy_policy_url
                )
            await workspace_form.save()

        existing_form = await self.form_service.get_form_document_by_id(str(form_id))

        if logo:
            logo_url = await self._aws_service.upload_file_to_s3(
                file=logo.file,
                key=str(form_id) + f"_logo{os.path.splitext(logo.filename)[1]}",
                previous_image=existing_form.logo,
            )
            form.logo = logo_url
        else:
            form.logo = form.logo if form.logo is not None else existing_form.logo
        if cover_image:
            cover_image_url = await self._aws_service.upload_file_to_s3(
                file=cover_image.file,
                key=str(form_id) + f"_cover{os.path.splitext(cover_image.filename)[1]}",
                previous_image=existing_form.cover_image,
            )
            form.cover_image = cover_image_url
        else:
            form.cover_image = (
                form.cover_image
                if form.cover_image is not None
                else existing_form.cover_image
            )
        return await self.form_service.update_form(form_id=form_id, form=form)

    async def upload_files_to_s3_and_update_url(self, form_files, response):
        for form_file in form_files:
            await self._aws_service.upload_file_to_s3(
                form_file.file.file, str(form_file.file_id), private=True
            )
            response.answers[form_file.field_id].file_metadata.url = ""
        return response

    async def submit_response(
        self,
        workspace_id: PydanticObjectId,
        form_id: PydanticObjectId,
        response: StandardFormResponse,
        user: User,
        form_files: list[FormFileResponse] = None,
    ):
        if form_files:
            response = await self.upload_files_to_s3_and_update_url(
                form_files, response
            )
        workspace_form_ids = (
            await self.workspace_form_repository.get_form_ids_in_workspace(
                workspace_id=workspace_id,
                is_not_admin=True,
                user=user,
                match_query={
                    "$or": [
                        {"form_id": str(form_id)},
                        {"settings.custom_url": str(form_id)},
                    ]
                },
            )
        )
        if not workspace_form_ids:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="Form not found"
            )
        if not response.dataOwnerIdentifier and user:
            response.dataOwnerIdentifier = user.sub
        return await self.form_response_service.submit_form_response(
            form_id=form_id, response=response, workspace_id=workspace_id
        )

    async def delete_form_response(
        self,
        workspace_id: PydanticObjectId,
        form_id: PydanticObjectId,
        response_id: PydanticObjectId,
        user: User,
    ):
        await self.workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        return await self.form_response_service.delete_form_response(
            form_id=form_id, response_id=response_id
        )


# async def upload_images_of_form
