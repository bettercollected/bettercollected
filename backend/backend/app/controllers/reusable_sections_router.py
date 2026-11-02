from http import HTTPStatus
from typing import List, Optional

from classy_fastapi import Routable, delete, get, patch, post, put
from common.ids import RecordId
from common.models.user import User
from fastapi import Depends, Query, Response

from backend.app.container import container
from backend.app.router import router
from backend.app.services.reusable_sections.service import (
    FragmentDto,
    PlanDto,
    PlanRequestDto,
    SectionContentDto,
    SectionCreateDto,
    SectionDetailsDto,
    SectionDto,
    SectionSummaryDto,
)
from backend.app.services.user_service import get_full_user


@router(
    prefix="/workspaces",
    tags=["Reusable sections"],
    responses={
        401: {"description": "Authorization token is missing."},
        403: {"description": "The caller lacks the permission."},
        404: {
            "description": "No such section in this workspace, or reusable sections "
            "are not available on this server."
        },
    },
)
class ReusableSectionsRouter(Routable):
    """A workspace's library of reusable sections (docs/reusable-sections.md).
    Reading needs ``form.read``; saving, renaming, deleting, inserting and
    updating a copy need ``form.edit``. Every section is looked up through the
    workspace."""

    @get("/{workspace_id}/sections")
    async def list_sections(
        self, workspace_id: RecordId, user: User = Depends(get_full_user)
    ) -> List[SectionSummaryDto]:
        return await container.reusable_section_service().list_sections(
            workspace_id, user
        )

    @post(
        "/{workspace_id}/sections",
        status_code=HTTPStatus.CREATED,
        responses={
            409: {"description": "name_taken"},
            422: {"description": "invalid_section, invalid_name, limit_reached"},
        },
    )
    async def create_section(
        self,
        workspace_id: RecordId,
        body: SectionCreateDto,
        user: User = Depends(get_full_user),
    ) -> SectionDto:
        return await container.reusable_section_service().create_section(
            workspace_id, body, user
        )

    @get("/{workspace_id}/sections/{section_id}")
    async def get_section(
        self,
        workspace_id: RecordId,
        section_id: str,
        version: Optional[int] = Query(None, ge=1),
        user: User = Depends(get_full_user),
    ) -> SectionDto:
        return await container.reusable_section_service().get_section(
            workspace_id, section_id, user, version=version
        )

    @patch(
        "/{workspace_id}/sections/{section_id}",
        responses={409: {"description": "name_taken"}},
    )
    async def update_section_details(
        self,
        workspace_id: RecordId,
        section_id: str,
        body: SectionDetailsDto,
        user: User = Depends(get_full_user),
    ) -> SectionSummaryDto:
        return await container.reusable_section_service().update_details(
            workspace_id, section_id, body, user
        )

    @put(
        "/{workspace_id}/sections/{section_id}/content",
        responses={
            409: {"description": "section_changed"},
            422: {"description": "invalid_section, limit_reached"},
        },
    )
    async def save_section_content(
        self,
        workspace_id: RecordId,
        section_id: str,
        body: SectionContentDto,
        user: User = Depends(get_full_user),
    ) -> SectionDto:
        return await container.reusable_section_service().save_content(
            workspace_id, section_id, body, user
        )

    @delete("/{workspace_id}/sections/{section_id}", status_code=HTTPStatus.NO_CONTENT)
    async def delete_section(
        self,
        workspace_id: RecordId,
        section_id: str,
        user: User = Depends(get_full_user),
    ) -> Response:
        await container.reusable_section_service().delete_section(
            workspace_id, section_id, user
        )
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @post("/{workspace_id}/sections/{section_id}/instantiate")
    async def instantiate_section(
        self,
        workspace_id: RecordId,
        section_id: str,
        user: User = Depends(get_full_user),
    ) -> FragmentDto:
        return await container.reusable_section_service().instantiate(
            workspace_id, section_id, user
        )

    @post("/{workspace_id}/sections/{section_id}/update-plan")
    async def update_plan(
        self,
        workspace_id: RecordId,
        section_id: str,
        body: PlanRequestDto,
        user: User = Depends(get_full_user),
    ) -> PlanDto:
        return await container.reusable_section_service().update_plan(
            workspace_id, section_id, body, user
        )
