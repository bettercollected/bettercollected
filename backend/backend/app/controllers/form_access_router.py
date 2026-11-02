from http import HTTPStatus
from typing import List, Literal

from classy_fastapi import Routable, delete, get, patch, post, put
from common.ids import RecordId
from common.models.user import User
from fastapi import Depends, Query, Response

from backend.app.container import container
from backend.app.router import router
from backend.app.services.form_access.admin import (
    CandidatesDto,
    FormAccessDto,
    ImpactDto,
    GrantDto,
    GrantRequestDto,
    MemberAccessDto,
    ModeRequestDto,
    TeamCreateDto,
    TeamDetailDto,
    TeamDto,
    TeamUpdateDto,
)
from backend.app.services.user_service import get_full_user


@router(
    prefix="/workspaces",
    tags=["Form access"],
    responses={
        401: {"description": "Authorization token is missing."},
        403: {"description": "The caller lacks the permission."},
        404: {"description": "Not found (also for another workspace's team, member, form or grant)."},
        422: {"description": "form_access_off, or a refused value."},
    },
)
class FormAccessRouter(Routable):
    """Teams (member groups), the grants on one form and a form's access mode
    (``FORM_ACCESS_ENABLED``; every route but ``GET .../access`` answers 422
    ``form_access_off`` while it is off). Teams need ``members.manage``;
    grants and the mode need ``form.share`` on the form, and on a restricted
    form only an owner, an admin or the form's creator manage them."""

    # -- teams ---------------------------------------------------------------
    @get("/{workspace_id}/member-groups")
    async def list_teams(
        self, workspace_id: RecordId, user: User = Depends(get_full_user)
    ) -> List[TeamDto]:
        return await container.form_access_admin_service().list_teams(workspace_id, user)

    @post(
        "/{workspace_id}/member-groups",
        status_code=HTTPStatus.CREATED,
        responses={409: {"description": "team_name_taken, too_many_teams"}},
    )
    async def create_team(
        self,
        workspace_id: RecordId,
        request: TeamCreateDto,
        user: User = Depends(get_full_user),
    ) -> TeamDto:
        return await container.form_access_admin_service().create_team(
            workspace_id, request, user
        )

    @get("/{workspace_id}/member-groups/{group_id}")
    async def get_team(
        self,
        workspace_id: RecordId,
        group_id: str,
        user: User = Depends(get_full_user),
    ) -> TeamDetailDto:
        return await container.form_access_admin_service().get_team(
            workspace_id, group_id, user
        )

    @patch(
        "/{workspace_id}/member-groups/{group_id}",
        responses={409: {"description": "team_name_taken"}},
    )
    async def update_team(
        self,
        workspace_id: RecordId,
        group_id: str,
        request: TeamUpdateDto,
        user: User = Depends(get_full_user),
    ) -> TeamDto:
        return await container.form_access_admin_service().update_team(
            workspace_id, group_id, request, user
        )

    @delete(
        "/{workspace_id}/member-groups/{group_id}", status_code=HTTPStatus.NO_CONTENT
    )
    async def delete_team(
        self,
        workspace_id: RecordId,
        group_id: str,
        user: User = Depends(get_full_user),
    ) -> Response:
        await container.form_access_admin_service().delete_team(
            workspace_id, group_id, user
        )
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @put(
        "/{workspace_id}/member-groups/{group_id}/members/{member_id}",
        status_code=HTTPStatus.NO_CONTENT,
        responses={409: {"description": "team_full"}},
    )
    async def add_team_member(
        self,
        workspace_id: RecordId,
        group_id: str,
        member_id: str,
        user: User = Depends(get_full_user),
    ) -> Response:
        await container.form_access_admin_service().add_team_member(
            workspace_id, group_id, member_id, user
        )
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @delete(
        "/{workspace_id}/member-groups/{group_id}/members/{member_id}",
        status_code=HTTPStatus.NO_CONTENT,
    )
    async def remove_team_member(
        self,
        workspace_id: RecordId,
        group_id: str,
        member_id: str,
        user: User = Depends(get_full_user),
    ) -> Response:
        await container.form_access_admin_service().remove_team_member(
            workspace_id, group_id, member_id, user
        )
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @get("/{workspace_id}/members/{member_id}/access")
    async def member_access(
        self,
        workspace_id: RecordId,
        member_id: str,
        user: User = Depends(get_full_user),
    ) -> MemberAccessDto:
        return await container.form_access_admin_service().member_access(
            workspace_id, member_id, user
        )

    # -- one form ------------------------------------------------------------
    @get("/{workspace_id}/forms/{form_id}/access")
    async def get_form_access(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: User = Depends(get_full_user),
    ) -> FormAccessDto:
        return await container.form_access_admin_service().get_access(
            workspace_id, form_id, user
        )

    @get("/{workspace_id}/forms/{form_id}/access/candidates")
    async def get_form_access_candidates(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: User = Depends(get_full_user),
    ) -> CandidatesDto:
        """The people (id, name) and teams (id, name, size) who could be given
        access to this form, for whoever may change its circle."""
        return await container.form_access_admin_service().candidates(
            workspace_id, form_id, user
        )

    @get("/{workspace_id}/forms/{form_id}/access/impact")
    async def get_form_access_impact(
        self,
        workspace_id: RecordId,
        form_id: str,
        mode: Literal["workspace", "restricted"] = Query(...),
        user: User = Depends(get_full_user),
    ) -> ImpactDto:
        """A dry run of the mode change: how many members would lose access."""
        return await container.form_access_admin_service().impact(
            workspace_id, form_id, mode, user
        )

    @put("/{workspace_id}/forms/{form_id}/access/mode")
    async def put_form_access_mode(
        self,
        workspace_id: RecordId,
        form_id: str,
        request: ModeRequestDto,
        user: User = Depends(get_full_user),
    ) -> FormAccessDto:
        return await container.form_access_admin_service().set_mode(
            workspace_id, form_id, request, user
        )

    @put(
        "/{workspace_id}/forms/{form_id}/grants",
        responses={
            403: {
                "description": "access_manage_forbidden, grant_above_own_role, "
                "export_grant_reserved, cannot_grant_self"
            },
            422: {"description": "form_access_off, privacy_officer_cannot_be_granted"},
        },
    )
    async def put_form_grant(
        self,
        workspace_id: RecordId,
        form_id: str,
        request: GrantRequestDto,
        user: User = Depends(get_full_user),
    ) -> GrantDto:
        return await container.form_access_admin_service().put_grant(
            workspace_id, form_id, request, user
        )

    @delete(
        "/{workspace_id}/forms/{form_id}/grants/{grant_id}",
        status_code=HTTPStatus.NO_CONTENT,
    )
    async def delete_form_grant(
        self,
        workspace_id: RecordId,
        form_id: str,
        grant_id: str,
        user: User = Depends(get_full_user),
    ) -> Response:
        await container.form_access_admin_service().delete_grant(
            workspace_id, form_id, grant_id, user
        )
        return Response(status_code=HTTPStatus.NO_CONTENT)
