import os
import re
from http import HTTPStatus
from typing import Optional

import bson
from beanie import PydanticObjectId
from common.constants import MESSAGE_FORBIDDEN
from common.models.user import User
from common.services.http_client import HttpClient
from fastapi import UploadFile
from loguru import logger
from pydantic import EmailStr

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.kafka_event_dto import UserEventType
from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.models.workspace import (
    WorkspaceRequestDtoCamel,
    WorkspaceResponseDto,
)
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.schemas.allowed_origin import AllowedOriginsDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.aws_service import AWSS3Service
from backend.app.services.form_response_service import FormResponseService
from backend.app.services.kafka_service import event_logger_service
from backend.app.services.responder_groups_service import ResponderGroupsService
from backend.app.services.user_tags_service import UserTagsService
from backend.app.services.workspace_form_service import WorkspaceFormService
from backend.app.services.workspace_user_service import WorkspaceUserService
from backend.config import settings


class WorkspaceService:
    def __init__(
        self,
        http_client: HttpClient,
        workspace_repo: WorkspaceRepository,
        aws_service: AWSS3Service,
        workspace_user_service: WorkspaceUserService,
        workspace_form_service: WorkspaceFormService,
        form_response_service: FormResponseService,
        responder_groups_service: ResponderGroupsService,
        user_tags_service: UserTagsService,
    ):
        self.http_client = http_client
        self._workspace_repo = workspace_repo
        self._aws_service = aws_service
        self._workspace_user_service = workspace_user_service
        self.workspace_form_service = workspace_form_service
        self.form_response_service = form_response_service
        self.responder_groups_service = responder_groups_service
        self.user_tags_service = user_tags_service

    async def get_workspace_by_id(self, workspace_id: PydanticObjectId):
        workspace = await self._workspace_repo.get_workspace_by_id(
            workspace_id=workspace_id
        )
        return WorkspaceResponseDto(**workspace.dict())

    async def get_workspace_by_query(self, query: str, user: User):
        workspace = await self._workspace_repo.get_workspace_by_query(query)
        if user:
            try:
                await self._workspace_user_service.check_user_has_access_in_workspace(
                    workspace_id=workspace.id, user=user
                )
                return WorkspaceResponseDto(**workspace.dict(), dashboard_access=True)
            except HTTPException:
                pass
        return WorkspaceResponseDto(**workspace.dict())

    async def create_non_default_workspace(
        self,
        title: str,
        description: str,
        user: User,
        workspace_name: str = None,
        profile_image_file: UploadFile = None,
        banner_image_file: UploadFile = None,
    ):
        if user.plan != "PRO":
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                content="Upgrade to Pro to add more workspace.",
            )

        user_owner_workspaces = await self._workspace_repo.get_user_workspaces(user.id)
        if len(user_owner_workspaces) >= settings.api_settings.ALLOWED_WORKSPACES:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT, content="Cannot add more workspaces"
            )
        if workspace_name:
            existing_workspace_with_name = await WorkspaceDocument.find_one(
                {"workspace_name": workspace_name}
            )
            if existing_workspace_with_name is not None:
                raise HTTPException(
                    HTTPStatus.CONFLICT,
                    content="Workspace with given name already exists.",
                )
        workspace_document = WorkspaceDocument(
            title=title,
            description=description,
            owner_id=user.id,
            workspace_name=workspace_name if workspace_name else str(bson.ObjectId()),
            is_pro=True,
        )
        workspace_document = await self.upload_images_of_workspace(
            workspace_document=workspace_document,
            profile_image_file=profile_image_file,
            banner_image_file=banner_image_file,
        )
        workspace_document = await workspace_document.save()
        existing_workspace_user = await WorkspaceUserDocument.find_one(
            {
                "workspace_id": workspace_document.id,
                "user_id": PydanticObjectId(user.id),
            }
        )
        if not existing_workspace_user:
            workspace_user = WorkspaceUserDocument(
                workspace_id=workspace_document.id,
                user_id=user.id,
                roles=[WorkspaceRoles.ADMIN],
            )
            await workspace_user.save()
        return WorkspaceResponseDto(**workspace_document.dict())

    async def patch_workspace(
        self,
        profile_image_file: UploadFile,
        banner_image_file: UploadFile,
        workspace_id,
        workspace_patch: WorkspaceRequestDtoCamel,
        user: User,
    ):
        await self._workspace_user_service.check_is_admin_in_workspace(
            workspace_id=workspace_id, user=user
        )
        workspace_document = await self._workspace_repo.get_workspace_by_id(
            workspace_id
        )
        if not str(workspace_document.owner_id) == user.id:
            return HTTPException(
                HTTPStatus.FORBIDDEN, "You are not authorized to perform this action."
            )

        workspace_document = await self.upload_images_of_workspace(
            workspace_document=workspace_document,
            profile_image_file=profile_image_file,
            banner_image_file=banner_image_file,
        )

        if (
            workspace_patch.workspace_name
            and workspace_patch.workspace_name != workspace_document.workspace_name
        ):
            exists_by_handle = await WorkspaceDocument.find_one(
                {"workspace_name": workspace_patch.workspace_name}
            )
            await self.user_tags_service.add_user_tag(
                user_id=user.id, tag=UserTagType.WORKSPACE_HANDLE_CHANGE
            )
            if exists_by_handle:
                raise HTTPException(409, "Workspace with given handle already exists.")

        workspace_document.workspace_name = (
            workspace_patch.workspace_name
            if workspace_patch.workspace_name
            else workspace_document.workspace_name
        )
        workspace_document.title = (
            workspace_patch.title if workspace_patch.title else workspace_document.title
        )
        workspace_document.description = (
            workspace_patch.description
            if workspace_patch.description
            else workspace_document.description
        )

        if workspace_patch.custom_domain:
            if not workspace_document.is_pro:
                raise HTTPException(status_code=403, content=MESSAGE_FORBIDDEN)

            try:
                workspace = await WorkspaceDocument.find_one(
                    {"custom_domain": workspace_patch.custom_domain}
                )
                if not workspace:
                    existing_custom_domain = (
                        workspace_document.custom_domain
                        if workspace_document.custom_domain
                        else ""
                    )
                    await AllowedOriginsDocument.find_one(
                        {"origin": "https://" + existing_custom_domain or ""}
                    ).delete()
                    allowed_origin = await AllowedOriginsDocument.find_one(
                        {"origin": "https://" + workspace_patch.custom_domain}
                    )
                    if not allowed_origin:
                        await AllowedOriginsDocument.save(
                            AllowedOriginsDocument(
                                origin="https://" + workspace_patch.custom_domain
                            )
                        )
                    await self.update_https_server_for_certificate(
                        old_domain=workspace_document.custom_domain,
                        new_domain=workspace_patch.custom_domain,
                    )
                    await self.user_tags_service.add_user_tag(
                        user_id=user.id, tag=UserTagType.CUSTOM_DOMAIN_UPDATED
                    )
                    await event_logger_service.send_event(
                        event_type=UserEventType.CUSTOM_DOMAIN_CHANGED,
                        user_id=user.id,
                        email=user.sub,
                    )
                else:
                    raise HTTPException(409)
            except HTTPException as e:
                if e.status_code == 409:
                    raise HTTPException(
                        409,
                        "Workspace with given custom domain already exists or Domain already exists.",
                    )

        workspace_document.custom_domain = (
            workspace_patch.custom_domain
            if workspace_patch.custom_domain
            else workspace_document.custom_domain
        )
        saved_workspace = await self._workspace_repo.update(
            workspace_document.id, workspace_document
        )
        return WorkspaceResponseDto(**saved_workspace.dict())

    async def delete_custom_domain_of_workspace(
        self, workspace_id: PydanticObjectId, user: User
    ):
        workspace_document = await self._workspace_repo.get_workspace_by_id(
            workspace_id=workspace_id
        )
        if not workspace_document.is_pro:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, content=MESSAGE_FORBIDDEN
            )
        await self._workspace_user_service.check_is_admin_in_workspace(
            workspace_id=workspace_id, user=user
        )
        workspace_document = await self._workspace_repo.get_workspace_by_id(
            workspace_id=workspace_id
        )
        await self.update_https_server_for_certificate(
            old_domain=workspace_document.custom_domain
        )
        workspace_document.custom_domain = ""
        saved_workspace = await workspace_document.save()
        return WorkspaceResponseDto(**saved_workspace.dict())

    async def generate_unique_names_from_the_workspace_handle(
        self, workspace_name: str, workspace_id: Optional[PydanticObjectId]
    ):
        suggestions = []
        clean_workspace_name = re.sub(r"\W+", "", workspace_name)
        is_valid_workspace_handle = await self.check_if_workspace_handle_is_unique(
            clean_workspace_name, workspace_id
        )
        if is_valid_workspace_handle:
            suggestions.append(clean_workspace_name)
        i = 1
        while 1:
            workspace_suggestion = clean_workspace_name + str(i)
            is_valid_workspace_handle = await self.check_if_workspace_handle_is_unique(
                workspace_suggestion, workspace_id
            )
            if is_valid_workspace_handle:
                suggestions.append(workspace_suggestion)
            if len(suggestions) == 6:
                break
            i += 1
        return suggestions

    async def check_if_workspace_handle_is_unique(
        self, workspace_name: str, workspace_id: Optional[PydanticObjectId]
    ):
        predefined_workspace_name = ["submissions", "forms", "templates"]
        if workspace_name in predefined_workspace_name:
            return False
        existing_workspace = await WorkspaceDocument.find_one(
            {"workspace_name": workspace_name}
        )
        if workspace_id is not None:
            current_workspace = await WorkspaceDocument.find_one({"_id": workspace_id})
            if existing_workspace and not existing_workspace == current_workspace:
                return False
            return True
        else:
            return existing_workspace is None

    async def get_mine_workspaces(self, user: User):
        workspace_ids = await self._workspace_user_service.get_mine_workspaces(user.id)
        workspaces = await self._workspace_repo.get_workspace_by_ids(
            workspace_ids=workspace_ids
        )
        return [WorkspaceResponseDto(**workspace.dict()) for workspace in workspaces]

    async def send_otp_for_workspace(
        self, workspace_id: PydanticObjectId, receiver_email: EmailStr
    ):
        workspace = await self._workspace_repo.get_workspace_by_id(workspace_id)
        await self.http_client.get(
            settings.auth_settings.BASE_URL + "/auth/otp/send",
            params={
                "receiver_email": receiver_email,
                "workspace_title": workspace.title,
                "workspace_profile_image": workspace.profile_image,
                "creator": False,
            },
            timeout=180,
        )
        return {"message": "Otp sent successfully"}

    async def get_workspace_stats(self, workspace_id: PydanticObjectId, user: User):
        await self._workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        form_ids = await self.workspace_form_service.get_form_ids_in_workspace(
            workspace_id=workspace_id
        )
        responses_count = (
            await self.form_response_service.get_responses_count_in_workspace(
                workspace_form_ids=form_ids
            )
        )
        deletion_count = (
            await self.form_response_service.get_deletion_requests_count_in_workspace(
                form_ids=form_ids
            )
        )

        return {
            "forms": len(form_ids),
            "responses": responses_count,
            "deletion_requests": deletion_count,
        }

    async def downgrade_user_workspace(self, user_id: str):
        workspaces = await self._workspace_repo.get_user_workspaces(owner_id=user_id)
        for workspace in workspaces:
            if not workspace.default:
                workspace.disabled = True
            workspace.is_pro = False
            workspace.custom_domain_disabled = True
            await workspace.save()
            await self._workspace_user_service.disable_other_users_in_workspace(
                workspace_id=workspace.id, user_id=PydanticObjectId(user_id)
            )

    async def upgrade_user_workspace(self, user_id: str):
        workspaces = await self._workspace_repo.get_user_workspaces(owner_id=user_id)
        for workspace in workspaces:
            workspace.disabled = False
            workspace.is_pro = True
            workspace.custom_domain_disabled = False
            await workspace.save()
            await self._workspace_user_service.enable_all_users_in_workspace(
                workspace_id=workspace.id
            )

    async def update_https_server_for_certificate(
        self, old_domain: str = None, new_domain: str = None
    ):
        try:
            if old_domain:
                await self.http_client.delete(
                    f"{settings.https_cert_api_settings.host}/domains",
                    headers={"api_key": settings.https_cert_api_settings.key},
                    params={"domain": new_domain},
                )
            if new_domain:
                await self.http_client.post(
                    f"{settings.https_cert_api_settings.host}/domains",
                    headers={"api_key": settings.https_cert_api_settings.key},
                    params={
                        "domain": new_domain,
                        "upstream": settings.https_cert_api_settings.upstream
                        if settings.https_cert_api_settings.upstream
                        else None,
                    },
                )
        except Exception as e:
            logger.error("Error form https server: ", e)
            # raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, content="Could not update https certificate.")

    async def upload_images_of_workspace(
        self,
        workspace_document: WorkspaceDocument,
        profile_image_file: UploadFile,
        banner_image_file: UploadFile,
    ):
        if profile_image_file:
            profile_image = await self._aws_service.upload_file_to_s3(
                profile_image_file.file,
                str(workspace_document.id)
                + f"profile{os.path.splitext(profile_image_file.filename)[1]}",
                workspace_document.profile_image,
            )
            workspace_document.profile_image = (
                profile_image if profile_image else workspace_document.profile_image
            )
        if banner_image_file:
            banner_image = await self._aws_service.upload_file_to_s3(
                banner_image_file.file,
                str(workspace_document.id)
                + f"banner{os.path.splitext(banner_image_file.filename)[1]}",
                workspace_document.banner_image,
            )
            workspace_document.banner_image = (
                banner_image if banner_image else workspace_document.banner_image
            )
        return workspace_document

    async def delete_workspaces_of_user_with_forms(self, user: User):
        workspaces = await self.get_mine_workspaces(user=user)
        workspaces = filter(lambda workspace: workspace.owner_id == user.id, workspaces)
        workspace_ids = [workspace.id for workspace in workspaces]
        form_ids = await self.workspace_form_service.get_form_ids_in_workspaces_and_imported_by_user(
            workspace_ids, user
        )
        await self.responder_groups_service.delete_groups_of_workspaces(
            workspace_ids=workspace_ids
        )
        await self.workspace_form_service.delete_forms_with_ids(form_ids=form_ids)
        await self._workspace_user_service.delete_user_form_all_workspaces(user)
        await self._workspace_user_service.delete_user_of_workspaces(
            workspace_ids=workspace_ids
        )
        await self._workspace_repo.delete_workspaces_with_ids(workspace_ids)


async def create_workspace(user: User):
    workspace = await WorkspaceDocument.find_one({"owner_id": user.id, "default": True})
    if not workspace:
        await event_logger_service.send_event(
            event_type=UserEventType.USER_CREATED, user_id=user.id, email=user.sub
        )
        workspace = WorkspaceDocument(
            title="",
            description="",
            owner_id=user.id,
            profile_image="",
            banner_image="",
            default=True,
            workspace_name=str(user.id),
            custom_domain=None,
        )
        await workspace.save()
    # Save new workspace user if it is not associated yet
    existing_workspace_user = await WorkspaceUserDocument.find_one(
        {"workspace_id": workspace.id, "user_id": PydanticObjectId(user.id)}
    )
    if not existing_workspace_user:
        workspace_user = WorkspaceUserDocument(
            workspace_id=workspace.id, user_id=user.id, roles=[WorkspaceRoles.ADMIN]
        )
        await workspace_user.save()
