"""Copy a form to another workspace (``FORM_PROMOTION_ENABLED``, docs/environments.md).

An environment is a workspace: development, staging and production are three of
them. These routes take a form's structure (its spec document) from one workspace
to another as a **draft**: a new form, or the draft of an existing one. Answers,
automations, sharing and the publish state never move. Every route needs a
signed-in person who may read the form in this workspace; the target workspace's
own permission is decided there (``form.create``, or ``form.edit`` on the form).

All four answer 422 ``form_promotion_disabled`` while the switch is off.
"""

from typing import Optional

from classy_fastapi import Routable, get, post
from common.ids import RecordId
from common.models.user import User
from fastapi import Depends, Header, Query, Request
from fastapi.responses import JSONResponse

from backend.app.container import container
from backend.app.models.dtos.form_promotion_dto import (
    ApplyRequest,
    PromotionApplied,
    PromotionRequest,
    PromotionTargetsDto,
)
from backend.app.router import router
from backend.app.services.form_promotion.mode import ensure_enabled
from backend.app.services.user_service import get_logged_user


@router(
    prefix="/workspaces/{workspace_id}/forms",
    tags=["Form promotion"],
    # first, before the body is read or anything is queried
    dependencies=[Depends(ensure_enabled)],
    responses={
        401: {"description": "Authorization token is missing."},
        403: {"description": "A permission is missing, on either side."},
        404: {"description": "No such form, or no such workspace for the caller."},
        422: {"description": "Switched off, or the form cannot be copied as it is."},
    },
)
class FormPromotionRouter(Routable):
    @get("/{form_id}/spec-file")
    async def download_spec_file(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: User = Depends(get_logged_user),
    ) -> JSONResponse:
        """The form's document as a file (it holds no answer), for taking the
        form to another instance. Needs ``form.read`` on the form; a restricted
        form only for an Owner, an Admin or its creator. Audited, never cached."""
        return await container.form_promotion_service().spec_file(
            user, workspace_id, form_id
        )

    @get("/{form_id}/promotion/targets", response_model=PromotionTargetsDto)
    async def promotion_targets(
        self,
        workspace_id: RecordId,
        form_id: str,
        target_workspace_id: RecordId = Query(..., alias="targetWorkspaceId"),
        q: Optional[str] = Query(None, max_length=200),
        user: User = Depends(get_logged_user),
    ):
        """The forms of the target workspace the caller may update, the ones last
        copied from this form first. ``q`` narrows by title."""
        return await container.form_promotion_service().targets(
            user, workspace_id, form_id, target_workspace_id, q
        )

    @post("/{form_id}/promotion/preview")
    async def preview_promotion(
        self,
        workspace_id: RecordId,
        form_id: str,
        body: PromotionRequest,
        user: User = Depends(get_logged_user),
    ):
        """What copying the form would do, stored nowhere: ``valid``, every error
        and warning of the target, the ``diff`` for an existing target, what is
        ``adjusted`` and ``notCarried`` (counts), and the ``sourceEtag`` and
        ``targetEtag`` to send back to apply."""
        return await container.form_promotion_service().preview(
            user, workspace_id, form_id, body
        )

    @post(
        "/{form_id}/promotion/apply",
        response_model=PromotionApplied,
        status_code=201,
        responses={
            200: {"description": "The target form's draft was updated."},
            400: {"description": "No (or an invalid) Idempotency-Key."},
            409: {
                "description": "A request with this Idempotency-Key still runs, or "
                "the target form changed since the last copy (target_changed)."
            },
            412: {"description": "Either form changed since the preview."},
        },
    )
    async def apply_promotion(
        self,
        workspace_id: RecordId,
        form_id: str,
        body: ApplyRequest,
        request: Request,
        idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
        user: User = Depends(get_logged_user),
    ):
        """Copy the form as a draft (never published), only while both forms are
        still the versions the preview showed. Answers 201 with the new form, 200
        with the updated one: ``{formId, workspaceId, created, etag}``."""
        return await container.form_promotion_service().apply(
            user, workspace_id, form_id, body, idempotency_key, request.url.path
        )
