"""The workspace's authenticator-app policy and the removal of a factor
(docs/totp.md). Owners set the policy and reset a member's factor; the platform
administrator can reset anyone's."""

from http import HTTPStatus

from classy_fastapi import Routable, delete, get, put
from common.ids import RecordId
from common.models.user import User
from fastapi import Depends
from starlette.responses import Response

from backend.app.container import container
from backend.app.router import router
from backend.app.services.mfa.workspace import SetTotpPolicyDto, TotpPolicyDto
from backend.app.services.user_service import get_full_user, get_logged_admin


@router(
    prefix="/workspaces",
    tags=["Workspace second factor"],
    responses={
        401: {"description": "Authorization token is missing."},
        403: {"description": "Not allowed (or mfa_required)."},
        422: {"description": "totp_off"},
    },
)
class WorkspaceTotpRouter(Routable):
    @get("/{workspace_id}/security/totp")
    async def overview(
        self, workspace_id: RecordId, user: User = Depends(get_full_user)
    ) -> TotpPolicyDto:
        """The setting and how many members have no authenticator app yet
        (``security.manage``)."""
        return await container.workspace_totp_service().overview(workspace_id, user)

    @put(
        "/{workspace_id}/security/totp",
        responses={409: {"description": "enrol_first"}},
    )
    async def set_required(
        self,
        workspace_id: RecordId,
        body: SetTotpPolicyDto,
        user: User = Depends(get_full_user),
    ) -> TotpPolicyDto:
        """Require an authenticator app for every member, or stop requiring one
        (owners only). Takes effect on the member's next request; nobody is
        signed out."""
        return await container.workspace_totp_service().set_required(
            workspace_id, user, body.required
        )

    @delete(
        "/{workspace_id}/members/{user_id}/totp",
        status_code=HTTPStatus.NO_CONTENT,
        responses={
            404: {"description": "Not a member, or no authenticator app."},
            409: {"description": "reset_self or reset_not_allowed"},
        },
    )
    async def reset_member(
        self,
        workspace_id: RecordId,
        user_id: str,
        user: User = Depends(get_full_user),
    ) -> Response:
        """Remove a member's authenticator app (owners only; see
        ``services/mfa/workspace.py`` for whose). Ends their sessions and mails
        them."""
        await container.workspace_totp_service().reset_member(
            workspace_id, user, user_id
        )
        return Response(status_code=HTTPStatus.NO_CONTENT)


@router(
    prefix="/admin/users",
    tags=["Platform administration"],
    responses={
        401: {"description": "Authorization token is missing."},
        403: {"description": "Only the platform administrator."},
    },
)
class AdminTotpRouter(Routable):
    @delete(
        "/{user_id}/totp",
        status_code=HTTPStatus.NO_CONTENT,
        responses={404: {"description": "No authenticator app."}},
    )
    async def reset(
        self, user_id: str, user: User = Depends(get_logged_admin)
    ) -> Response:
        """Remove anyone's authenticator app (never one's own). Ends their
        sessions and mails them."""
        await container.workspace_totp_service().admin_reset(user, user_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)
