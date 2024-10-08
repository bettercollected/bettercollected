import os
import random
import re
from http import HTTPStatus
from typing import List, Optional, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from beanie import PydanticObjectId
from common.configs.crypto import Crypto
from common.constants import MESSAGE_NOT_FOUND, MESSAGE_FORBIDDEN
from common.enums.plan import Plans
from common.models.form_import import FormImportRequestBody
from common.models.standard_form import (
    StandardForm,
    StandardFormResponse,
    Trigger,
    StandardFormSettings,
)
from common.models.user import User
from fastapi import UploadFile
from starlette.requests import Request

from backend.app.exceptions import HTTPException
from backend.app.models.dataclasses.user_tokens import UserTokens
from backend.app.models.dtos.action_dto import AddActionToFormDto, UpdateActionInFormDto
from backend.app.models.dtos.brevo_event_dto import UserEventType
from backend.app.models.dtos.response_dtos import (
    FormFileResponse,
    StandardFormCamelModel,
    StandardFormResponseCamelModel,
)
from backend.app.models.workspace import WorkspaceFormSettings, WorkspaceRequestDto
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.schedulers.form_schedular import FormSchedular
from backend.app.schemas.form_versions import FormVersionsDocument
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.template import FormTemplateDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.app.services.actions_service import ActionService
from backend.app.services.aws_service import AWSS3Service
from backend.app.services.form_import_service import FormImportService
from backend.app.services.form_plugin_provider_service import FormPluginProviderService
from backend.app.services.form_response_service import FormResponseService
from backend.app.services.form_service import FormService
from backend.app.services.brevo_service import event_logger_service
from backend.app.services.plugin_proxy_service import PluginProxyService
from backend.app.services.responder_groups_service import ResponderGroupsService
from backend.app.services.temporal_service import TemporalService
from backend.app.services.user_tags_service import UserTagsService
from backend.app.services.workspace_user_service import WorkspaceUserService
from backend.app.utils import AiohttpClient
from backend.app.utils.hash import hash_string
from backend.config import settings

crypto = Crypto(settings.auth_settings.AES_HEX_KEY)


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
        action_service: ActionService,
        crypto: Crypto,
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
        self.action_service = action_service
        self.crypto = crypto

    async def check_form_exists_in_workspace(
        self, workspace_id: PydanticObjectId, form_id: str
    ):
        if not await self.workspace_form_repository.check_if_form_exists_in_workspace(
            workspace_id=workspace_id, form_id=form_id
        ):
            raise HTTPException(HTTPStatus.NOT_FOUND, MESSAGE_NOT_FOUND)

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
        workspace_form = await self.workspace_form_repository.get_workspace_form_with_custom_slug_form_id(
            workspace_id=workspace_id, custom_url=standard_form.form_id
        )
        if not workspace_form:
            normalized_custom_slug = self.clean_and_normalize_string(
                standard_form.title
            )
            existing_workspace_form = await self.workspace_form_repository.get_workspace_form_with_custom_slug_form_id(
                workspace_id=workspace_id, custom_url=normalized_custom_slug
            )
            if existing_workspace_form:
                while True:
                    new_normalized_string = (
                        normalized_custom_slug + "-" + str(random.randint(0, 1000))
                    )
                    existing_workspace_form = await self.workspace_form_repository.get_workspace_form_with_custom_slug_form_id(
                        workspace_id=workspace_id, custom_url=new_normalized_string
                    )
                    if not existing_workspace_form:
                        normalized_custom_slug = new_normalized_string
                        break

            workspace_form = await self.workspace_form_repository.save_workspace_form(
                workspace_id=workspace_id,
                form_id=standard_form.form_id,
                user_id=user.id,
                workspace_form_settings=WorkspaceFormSettings(
                    custom_url=normalized_custom_slug,
                    embed_url=embed_url,
                    response_data_owner_field=form_import.response_data_owner,
                    # TODO : Refactor repeated information provider is only saved on form
                    #  as it doesn't change with workspaces
                    provider=standard_form.settings.provider,
                    private=not standard_form.settings.is_public,
                ),
            )

        await event_logger_service.send_event(
            event_type=UserEventType.FORM_IMPORTED, user_id=user.id, email=user.sub
        )

        response_dict = {**standard_form.dict(), "settings": workspace_form.settings}
        return StandardFormCamelModel(**response_dict)

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

        form = await self.form_service.get_form_document_by_id(form_id)
        if form and form.imported_form_id:
            await FormVersionsDocument.find(
                {"imported_form_id": form.imported_form_id}
            ).delete()
        await self.form_service.delete_form(form_id=form_id)
        await self.form_response_service.delete_form_responses(form_id=form_id)
        await self.form_response_service.delete_deletion_requests(form_id=form_id)
        await self.responder_groups_service.responder_groups_repo.delete_workspace_form_groups(
            form_id=form_id
        )
        self._aws_service.delete_folder_from_s3(f"private/{workspace_id}/{form_id}")

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

    async def add_groups_to_form(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        group_ids: List[PydanticObjectId],
        user: User,
    ):
        await self.workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        return await self.responder_groups_service.add_groups_to_form(
            form_id=form_id, group_ids=group_ids
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

    def generate_presigned_file_url(
        self,
        key: str,
    ):
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
        settings = (
            form.settings
            if form.settings
            else StandardFormSettings(
                privacy_policy_url="",
                response_expiration="",
                response_expiration_type=None,
                response_data_owner_field="",
            )
        )

        workspace_form_settings = WorkspaceFormSettings(
            custom_url=form.form_id,
            provider="self",
            privacy_policy_url=settings.privacy_policy_url,
            response_expiration=settings.response_expiration,
            response_expiration_type=settings.response_expiration_type,
            response_data_owner_field=(settings.response_data_owner_field),
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
            if form.settings.response_expiration is not None:
                workspace_form.settings.response_expiration = (
                    form.settings.response_expiration
                )
            if form.settings.response_expiration_type is not None:
                workspace_form.settings.response_expiration_type = (
                    form.settings.response_expiration_type
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

    async def upload_files_to_s3_and_update_url(
        self,
        form_files,
        response: StandardFormResponseCamelModel,
        workspace_id: Optional[str] = "",
        form_id: Optional[str] = "",
    ):
        for form_file in form_files:
            folder_name = (
                f"private/{workspace_id}/{form_id}/{response.response_id}"
                if workspace_id and form_id
                else "private"
            )
            await self._aws_service.upload_file_to_s3(
                file=form_file.file.file,
                key=str(form_file.file_id),
                private=True,
                folder_name=folder_name,
            )
        return response

    async def patch_response(
        self,
        workspace_id: PydanticObjectId,
        form_id: PydanticObjectId,
        response_id: PydanticObjectId,
        form_files: Optional[Any],
        response: StandardFormResponseCamelModel,
        user: User,
    ):
        if form_files:
            response = await self.upload_files_to_s3_and_update_url(
                form_files=form_files, response=response
            )
        workspace_forms = (
            await self.workspace_form_repository.get_workspace_forms_in_workspace(
                workspace_id=workspace_id,
                is_not_admin=True,
                user=user,
                match_query={"form_id": str(form_id)},
            )
        )

        if not workspace_forms or len(workspace_forms) == 0:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="Form not found"
            )

        workspace_form = workspace_forms[0]
        workspace_form = WorkspaceFormDocument(**workspace_form)

        if (
            not workspace_form.settings.require_verified_identity
            or not workspace_form.settings.allow_editing_response
        ):
            raise HTTPException(HTTPStatus.FORBIDDEN, content=MESSAGE_FORBIDDEN)

        form_response = await self.form_response_service.patch_form_response(
            workspace_id=workspace_id,
            form_id=form_id,
            response_id=response_id,
            response=response,
            user=user,
        )

        return form_response.submission_uuid

    async def submit_response(
        self,
        workspace_id: PydanticObjectId,
        form_id: PydanticObjectId,
        response: StandardFormResponse,
        user: User,
        form_files: list[FormFileResponse] = None,
    ):
        response.response_id = str(PydanticObjectId())
        if form_files:
            response = await self.upload_files_to_s3_and_update_url(
                form_files,
                response,
                workspace_id=str(workspace_id),
                form_id=str(form_id),
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

        form_response = await self.form_response_service.submit_form_response(
            form_id=form_id, response=response, workspace_id=workspace_id
        )

        form = await self.form_service.get_form_document_by_id(form_id=str(form_id))

        # TODO: get latest version of form from form_service

        latest_version_of_form = await self.form_service.get_latest_version_of_form(
            form_id=form_id
        )
        latest_version_of_form.actions = form.actions
        latest_version_of_form.secrets = form.secrets
        latest_version_of_form.parameters = form.parameters

        # TODO resolve circular deps for workspace service to get workspace details
        # workspace = await WorkspaceDocument.find_one(WorkspaceDocument.id == workspace_id)
        # workspace = await self.workspace_repo.get_workspace_with_action_by_id(workspace_id)
        await self.action_service.start_actions_for_submission(
            form=latest_version_of_form,
            response=form_response,
            workspace_id=workspace_id,
        )
        return form_response

    async def delete_form_response(
        self,
        workspace_id: PydanticObjectId,
        form_id: PydanticObjectId,
        response_id: str,
        user: User,
    ):
        await self.workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        return await self.form_response_service.delete_form_response(
            form_id=form_id, response_id=response_id, workspace_id=workspace_id
        )

    async def publish_form(
        self, workspace_id: PydanticObjectId, form_id: PydanticObjectId, user: User
    ):
        await self.workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        return await self.form_service.publish_form(form_id=form_id)

    async def get_form_workspace_by_id(self, workspace_id: PydanticObjectId):
        return await self.form_import_service.get_form_workspace_by_id(
            workspace_id=workspace_id
        )

    # for duplicate and template of form
    async def duplicate_form(
        self,
        workspace_id: PydanticObjectId,
        form_id: PydanticObjectId,
        user: User,
        is_template: bool = False,
        user_tokens: UserTokens = None,
    ):
        await self.workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        workspace_form = (
            await self.workspace_form_repository.get_workspace_form_in_workspace(
                workspace_id=workspace_id, query=str(form_id)
            )
        )
        if not workspace_form:
            raise HTTPException(HTTPStatus.NOT_FOUND, MESSAGE_NOT_FOUND)
        form = await self.form_service.get_form_document_by_id(form_id=str(form_id))
        duplicated_form = FormTemplateDocument() if is_template else FormDocument()
        duplicated_form.fields = form.fields
        duplicated_form.logo = form.logo
        duplicated_form.builder_version = form.builder_version
        duplicated_form.cover_image = form.cover_image
        duplicated_form.welcome_page = form.welcome_page
        duplicated_form.thankyou_page = form.thankyou_page
        duplicated_form.theme = form.theme
        duplicated_form.title = (
            form.title
            if is_template
            else (form.title if form.title else "Untitled") + " (Copy)"
        )
        duplicated_form.description = form.description
        duplicated_form.button_text = form.button_text
        if is_template:
            duplicated_form.workspace_id = workspace_id
            duplicated_form.created_by = user.id
        else:
            duplicated_form.form_id = str(PydanticObjectId())
        duplicated_form = await duplicated_form.save()

        if is_template and settings.schedular_settings.ENABLED:
            await self.temporal_service.start_save_preview_workflow(
                duplicated_form.id, user_tokens=user_tokens
            )
        if not is_template:
            workspace_form = WorkspaceFormDocument(
                form_id=str(duplicated_form.form_id),
                workspace_id=workspace_id,
                user_id=user.id,
                settings=WorkspaceFormSettings(),
            )
            workspace_form.settings.provider = "self"
            workspace_form.settings.custom_url = str(duplicated_form.id)
            workspace_form = await workspace_form.save()
            duplicated_form.settings = workspace_form.settings
        return duplicated_form

    async def add_action_to_form(
        self,
        workspace_id: PydanticObjectId,
        form_id: PydanticObjectId,
        add_action_to_form_params: AddActionToFormDto,
        user: User,
    ):
        await self.check_form_exists_in_workspace(
            workspace_id=workspace_id, form_id=str(form_id)
        )
        await self.workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        action = await self.action_service.get_action_by_id(
            action_id=add_action_to_form_params.action_id
        )
        if action is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content=MESSAGE_NOT_FOUND
            )
        await self.action_service.create_action_in_workspace_from_action(
            workspace_id=workspace_id, action=action, user=user
        )
        updated_form = await self.form_service.add_action_form(
            form_id=form_id,
            add_action_to_form_params=add_action_to_form_params,
            action=action,
        )
        return updated_form.actions

    async def remove_action_from_form(
        self,
        workspace_id: PydanticObjectId,
        form_id: PydanticObjectId,
        action_id: PydanticObjectId,
        trigger: Trigger,
        user: User,
    ):
        await self.check_form_exists_in_workspace(
            workspace_id=workspace_id, form_id=str(form_id)
        )
        await self.workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        return await self.form_service.remove_action_from_form(
            form_id=form_id, action_id=action_id, trigger=trigger
        )

    async def update_action_status_in_form(
        self,
        workspace_id: PydanticObjectId,
        form_id: PydanticObjectId,
        update_action_dto: UpdateActionInFormDto,
        user: User,
    ):
        await self.check_form_exists_in_workspace(
            workspace_id=workspace_id, form_id=str(form_id)
        )
        await self.workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        await self.form_service.update_state_of_action_in_form(
            form_id=form_id, update_action_dto=update_action_dto
        )

    def clean_and_normalize_string(self, input_string):
        # Remove special characters, keep only alphanumeric and spaces
        cleaned_string = re.sub("[^a-zA-Z0-9\s]", "", input_string)

        # Replace multiple consecutive spaces with a single space
        cleaned_string = re.sub("\s+", " ", cleaned_string)

        # Remove spaces at the beginning and end of the string
        cleaned_string = cleaned_string.strip()

        # Replace spaces with hyphens and reduce consecutive hyphens to a single hyphen
        cleaned_string = re.sub(r"[^a-zA-Z0-9]+", "-", cleaned_string)

        # Convert the string to lowercase
        cleaned_string = cleaned_string.lower()

        return cleaned_string

    async def update_action_from_temporal(
        self,
        workspace_id: PydanticObjectId,
        form_id: PydanticObjectId,
        action_id: PydanticObjectId,
    ):
        form = await self.form_service.get_form_document_by_id(str(form_id))
        form_action = [
            action
            for action in form.actions[Trigger.on_submit]
            if action.id == action_id
        ][0]
        form_action.enabled = False
        await form.save()
        return form
