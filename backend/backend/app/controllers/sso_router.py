from http import HTTPStatus

from beanie import PydanticObjectId
from classy_fastapi import Routable, delete, get, post, put
from common.models.user import User
from fastapi import Depends, Request, Response
from starlette.responses import RedirectResponse

from backend.app.container import container
from backend.app.router import router
from backend.app.services.sso.connection_service import (
    CreateSsoConnectionDto,
    SsoConnectionDto,
    SsoOverviewDto,
    SsoSettingsDto,
    UpdateSsoSettingsDto,
)
from backend.app.services.sso.login_service import SsoRefused
from backend.app.services.user_service import get_logged_user


@router(
    prefix="/workspaces",
    tags=["Workspace single sign-on"],
    responses={
        401: {"description": "Authorization token is missing."},
        403: {"description": "Only the workspace owner and admins manage SSO."},
    },
)
class WorkspaceSsoRouter(Routable):
    """Single sign-on connections and settings of a workspace (docs/sso.md).
    Every route needs ``security.manage`` (Owner, Admin)."""

    @get("/{workspace_id}/sso")
    async def overview(
        self, workspace_id: PydanticObjectId, user: User = Depends(get_logged_user)
    ) -> SsoOverviewDto:
        return await container.sso_connection_service().overview(workspace_id, user)

    @post(
        "/{workspace_id}/sso/connections",
        status_code=HTTPStatus.CREATED,
        responses={
            404: {"description": "SSO is not enabled on this instance."},
            409: {"description": "The identity provider is already connected."},
            422: {"description": "Invalid metadata, URL or OIDC client."},
        },
    )
    async def create_connection(
        self,
        workspace_id: PydanticObjectId,
        request: CreateSsoConnectionDto,
        user: User = Depends(get_logged_user),
    ) -> SsoConnectionDto:
        return await container.sso_connection_service().create_connection(
            workspace_id, request, user
        )

    @post("/{workspace_id}/sso/connections/{connection_id}/enable")
    async def enable_connection(
        self,
        workspace_id: PydanticObjectId,
        connection_id: str,
        user: User = Depends(get_logged_user),
    ) -> SsoConnectionDto:
        return await container.sso_connection_service().enable_connection(
            workspace_id, connection_id, user
        )

    @post("/{workspace_id}/sso/connections/{connection_id}/disable")
    async def disable_connection(
        self,
        workspace_id: PydanticObjectId,
        connection_id: str,
        user: User = Depends(get_logged_user),
    ) -> SsoConnectionDto:
        return await container.sso_connection_service().disable_connection(
            workspace_id, connection_id, user
        )

    @delete(
        "/{workspace_id}/sso/connections/{connection_id}",
        status_code=HTTPStatus.NO_CONTENT,
    )
    async def delete_connection(
        self,
        workspace_id: PydanticObjectId,
        connection_id: str,
        user: User = Depends(get_logged_user),
    ) -> Response:
        await container.sso_connection_service().delete_connection(
            workspace_id, connection_id, user
        )
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @get("/{workspace_id}/sso/connections/{connection_id}/test")
    async def test_connection(
        self,
        workspace_id: PydanticObjectId,
        connection_id: str,
        request: Request,
        user: User = Depends(get_logged_user),
    ):
        """Browser navigation: sign in at the identity provider once; the
        outcome comes back to the SSO settings page as ``sso_test=``."""
        try:
            url = await container.sso_login_service().test_url(
                workspace_id, connection_id, user, request.headers.get("referer")
            )
        except SsoRefused as refused:
            return RedirectResponse(refused.redirect)
        return RedirectResponse(url)

    @put("/{workspace_id}/sso/settings")
    async def update_settings(
        self,
        workspace_id: PydanticObjectId,
        request: UpdateSsoSettingsDto,
        user: User = Depends(get_logged_user),
    ) -> SsoSettingsDto:
        return await container.sso_connection_service().update_settings(
            workspace_id, request, user
        )
