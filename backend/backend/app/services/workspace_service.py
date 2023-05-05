import os
from http import HTTPStatus

from beanie import PydanticObjectId
from fastapi import UploadFile
from loguru import logger
from pydantic import EmailStr

from backend.app.exceptions import HTTPException
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
from backend.app.services.workspace_form_service import WorkspaceFormService
from backend.app.services.workspace_user_service import WorkspaceUserService
from backend.config import settings
from common.constants import MESSAGE_FORBIDDEN
from common.enums.plan import Plans
from common.models.user import User
from common.services.http_client import HttpClient


class WorkspaceService:
    def __init__(
        self,
        http_client: HttpClient,
        workspace_repo: WorkspaceRepository,
        aws_service: AWSS3Service,
        workspace_user_service: WorkspaceUserService,
        workspace_form_service: WorkspaceFormService,
        form_response_service: FormResponseService,
    ):
        self.http_client = http_client
        self._workspace_repo = workspace_repo
        self._aws_service = aws_service
        self._workspace_user_service = workspace_user_service
        self.workspace_form_service = workspace_form_service
        self.form_response_service = form_response_service

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

        if workspace_patch.workspace_name:
            exists_by_handle = await WorkspaceDocument.find_one(
                {"workspace_name": workspace_patch.workspace_name}
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
            if user.plan == Plans.FREE:
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
        if user.plan == Plans.FREE:
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
        workspace_document.custom_domain = None
        saved_workspace = await self._workspace_repo.update(
            workspace_id, workspace_document
        )
        return WorkspaceResponseDto(**saved_workspace.dict())

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
        workspace = await self._workspace_repo.get_workspace_by_owner_id(
            owner_id=user_id
        )
        workspace.custom_domain_disabled = True
        await workspace.save()
        await self._workspace_user_service.disable_other_users_in_workspace(
            workspace_id=workspace.id, user_id=PydanticObjectId(user_id)
        )

    async def upgrade_user_workspace(self, user_id: str):
        workspace = await self._workspace_repo.get_workspace_by_owner_id(
            owner_id=user_id
        )
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
                    params={"host": new_domain},
                )
            if new_domain:
                await self.http_client.post(
                    f"{settings.https_cert_api_settings.host}/domains",
                    headers={"api_key": settings.https_cert_api_settings.key},
                    params={"host": new_domain},
                )
        except Exception as e:
            logger.error("Error form https server: ", e)
            # raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, content="Could not update https certificate.")


async def create_workspace(user: User):
    workspace = await WorkspaceDocument.find_one({"owner_id": user.id, "default": True})
    if not workspace:
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
