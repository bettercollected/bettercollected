from http import HTTPStatus

from beanie import PydanticObjectId
from classy_fastapi import Routable, delete, get, post, put
from common.models.user import User
from fastapi import Depends, Request, Response
from fastapi.responses import JSONResponse

from backend.app.container import container
from backend.app.router import router
from backend.app.services.scim.directory_service import (
    CreateDirectoryDto,
    DirectoryCredentialsDto,
    DirectoryOverviewDto,
    GroupDto,
    GroupRoleDto,
    ResyncDto,
)
from backend.app.services.user_service import get_full_user
from backend.config import settings


@router(
    prefix="/workspaces",
    tags=["Workspace directory sync (SCIM)"],
    responses={
        401: {"description": "Authorization token is missing."},
        403: {"description": "Only the workspace owner changes directory sync."},
    },
)
class WorkspaceScimRouter(Routable):
    """A workspace's SCIM directory (docs/sso.md, "Directory sync"). Viewing
    needs ``security.manage`` (Owner, Admin); every change is Owner only."""

    @get("/{workspace_id}/scim")
    async def overview(
        self, workspace_id: PydanticObjectId, user: User = Depends(get_full_user)
    ) -> DirectoryOverviewDto:
        return await container.scim_directory_service().overview(workspace_id, user)

    @post(
        "/{workspace_id}/scim/directory",
        status_code=HTTPStatus.CREATED,
        responses={
            404: {"description": "Directory sync is not enabled on this instance."},
            409: {"description": "No verified domain, or a directory exists."},
        },
    )
    async def create_directory(
        self,
        workspace_id: PydanticObjectId,
        request: CreateDirectoryDto,
        user: User = Depends(get_full_user),
    ) -> DirectoryCredentialsDto:
        """The SCIM base URL and bearer token are in this reply only."""
        return await container.scim_directory_service().create(
            workspace_id, request, user
        )

    @post("/{workspace_id}/scim/directory/rotate")
    async def rotate_token(
        self, workspace_id: PydanticObjectId, user: User = Depends(get_full_user)
    ) -> DirectoryCredentialsDto:
        return await container.scim_directory_service().rotate(workspace_id, user)

    @delete("/{workspace_id}/scim/directory", status_code=HTTPStatus.NO_CONTENT)
    async def delete_directory(
        self, workspace_id: PydanticObjectId, user: User = Depends(get_full_user)
    ) -> Response:
        await container.scim_directory_service().delete(workspace_id, user)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @put("/{workspace_id}/scim/groups/{group_id}")
    async def set_group_role(
        self,
        workspace_id: PydanticObjectId,
        group_id: str,
        request: GroupRoleDto,
        user: User = Depends(get_full_user),
    ) -> GroupDto:
        return await container.scim_directory_service().set_group_role(
            workspace_id, group_id, request, user
        )

    @post("/{workspace_id}/scim/resync")
    async def resync(
        self, workspace_id: PydanticObjectId, user: User = Depends(get_full_user)
    ) -> ResyncDto:
        return await container.scim_directory_service().resync(workspace_id, user)


@router(prefix="/scim", tags=["Directory sync webhook"])
class ScimWebhookRouter(Routable):
    """Polis's signed directory events. No session or key: the
    ``BoxyHQ-Signature`` HMAC with the directory's secret is the only
    authentication, checked before anything else is read."""

    @post(
        "/webhook/{directory_id}",
        responses={
            401: {"description": "Missing or invalid signature, or unknown directory."},
            403: {"description": "The event is for another tenant or directory."},
        },
    )
    async def webhook(self, directory_id: str, request: Request):
        declared = request.headers.get("content-length")
        if (
            declared
            and declared.isdigit()
            and (int(declared) > settings.scim.MAX_WEBHOOK_BYTES)
        ):
            return JSONResponse({"code": "too_large"}, status_code=413)
        body = await request.body()
        reply = await container.scim_webhook_service().receive(
            directory_id, request.headers, body
        )
        return JSONResponse(reply.body, status_code=reply.status)
