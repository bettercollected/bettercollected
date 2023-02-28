import os
from http import HTTPStatus

from beanie import PydanticObjectId
from fastapi import UploadFile
from pydantic import EmailStr

from backend.app.models.workspace import WorkspaceRequestDto, WorkspaceResponseDto
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.aws_service import AWSS3Service
from backend.config import settings
from common.exceptions.http import HTTPException
from common.models.user import User
from common.services.http_client import HttpClient


class WorkspaceService:
    def __init__(
            self,
            http_client: HttpClient,
            workspace_repo: WorkspaceRepository,
            aws_service: AWSS3Service,
            workspace_user_repo: WorkspaceUserRepository,
    ):
        self.http_client = http_client
        self._workspace_repo = workspace_repo
        self._aws_service = aws_service
        self._workspace_user_repo = workspace_user_repo

    async def get_workspace_by_id(self, workspace_id: PydanticObjectId):
        workspace = await self._workspace_repo.get_workspace_by_id(
            workspace_id=workspace_id
        )
        return WorkspaceResponseDto(**workspace.dict())

    async def get_workspace_by_query(self, query: str):
        workspace = await self._workspace_repo.get_workspace_by_query(query)
        return WorkspaceResponseDto(**workspace.dict())

    async def patch_workspace(
            self,
            profile_image_file: UploadFile,
            banner_image_file: UploadFile,
            workspace_id,
            workspace_patch: WorkspaceRequestDto,
            user: User,
    ):
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
                {"workspaceName": workspace_patch.workspace_name}
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
        workspace_document.owner_id = (
            workspace_patch.owner_id
            if workspace_patch.owner_id
            else workspace_document.owner_id
        )

        if workspace_patch.custom_domain:
            try:
                await self.get_workspace_by_query(workspace_patch.custom_domain)
                raise HTTPException(409)
            except HTTPException as e:
                if e.status_code == 409:
                    raise HTTPException(
                        409, "Workspace with given custom domain already exists!"
                    )
                pass

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
        await self._workspace_user_repo.is_user_admin_in_workspace(workspace_id, user)
        workspace_document = await self._workspace_repo.get_workspace_by_id(
            workspace_id=workspace_id
        )
        workspace_document.customDomain = None
        saved_workspace = await self._workspace_repo.update(
            workspace_id, workspace_document
        )
        return WorkspaceResponseDto(**saved_workspace.dict())

    async def get_mine_workspaces(self, user: User):
        workspaces = await self._workspace_repo.get_user_workspaces(user.id)
        return [WorkspaceResponseDto(**workspace.dict()) for workspace in workspaces]

    async def send_otp_for_workspace(self, workspace_id: PydanticObjectId, receiver_email: EmailStr):
        workspace = await self._workspace_repo.get_workspace_by_id(workspace_id)
        response_data = await self.http_client.get(
            settings.auth_settings.AUTH_BASE_URL + "/auth/otp/send",
            params={"receiver_email": receiver_email, "workspace_title": workspace.title},
            timeout=180
        )
        return {"message": "Otp sent successfully"}


async def create_workspace(user: User):
    workspace = await WorkspaceDocument.find_one({"ownerId": user.id, "default": True})
    if not workspace:
        workspace = WorkspaceDocument(
            title="Untitled",
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
            {"workspace_id": workspace.id, "user_id": user.id}
        )
        if not existing_workspace_user:
            workspace_user = WorkspaceUserDocument(
                workspace_id=workspace.id, user_id=user.id
            )
            await workspace_user.save()
