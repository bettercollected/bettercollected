"""A form's published versions for staff (docs: backend/AGENTS.md, "Form
versions page"): list, compare, restore into the draft. All behind
``FORM_REVISIONS_UI_ENABLED`` (422 ``form_revisions_disabled`` while off).
Reading one version stays ``GET .../versions/{version}`` (workspace_forms)."""

from typing import Optional

from classy_fastapi import Routable, get, post
from common.ids import RecordId
from common.models.user import User
from fastapi import Depends, Query

from backend.app.container import container
from backend.app.models.dtos.form_versions_dto import (
    FormVersionListDto,
    RestoreVersionRequest,
    RestoreVersionResponse,
    VersionCompareDto,
)
from backend.app.router import router
from backend.app.services.user_service import get_logged_user


@router(
    prefix="/workspaces/{workspace_id}/forms",
    tags=["Form versions"],
    responses={
        401: {"description": "Authorization token is missing."},
        403: {"description": "The permission is missing."},
        404: {"description": "Not Found"},
        422: {"description": "The versions page is switched off, or the input is not valid."},
    },
)
class FormVersionsRouter(Routable):
    @get("/{form_id}/versions", response_model=FormVersionListDto)
    async def list_form_versions(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: User = Depends(get_logged_user),
    ):
        """The published versions of a form, newest first (``form.read``):
        number, when, by whom (the member's current name), and the draft's
        state. No answers, no response counts."""
        return await container.form_versions_service().list_versions(
            workspace_id, form_id, user
        )

    @get("/{form_id}/version-diff", response_model=VersionCompareDto)
    async def compare_form_versions(
        self,
        workspace_id: RecordId,
        form_id: str,
        from_version: Optional[str] = Query(None, alias="from"),
        to_version: Optional[str] = Query(None, alias="to"),
        user: User = Depends(get_logged_user),
    ):
        """What changed going from ``from`` to ``to`` (a version number or
        ``draft``), as coded entries the dashboard words in the viewer's
        language (``form.read``)."""
        return await container.form_versions_service().compare(
            workspace_id, form_id, from_version, to_version, user
        )

    @post(
        "/{form_id}/versions/{version}/restore", response_model=RestoreVersionResponse
    )
    async def restore_form_version(
        self,
        workspace_id: RecordId,
        form_id: str,
        version: int,
        body: RestoreVersionRequest,
        user: User = Depends(get_logged_user),
    ):
        """Replace the draft's content with a version's (``form.edit``).
        Nothing is published and no version changes: publish the draft to make
        a new version. 409 ``form_changed`` when the draft moved on since
        ``expectedUpdatedAt``, 409 ``draft_has_changes`` unless
        ``replaceDraft`` is true while the draft holds unpublished work."""
        return await container.form_versions_service().restore(
            workspace_id, form_id, version, body, user
        )
