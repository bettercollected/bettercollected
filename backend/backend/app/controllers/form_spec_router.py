"""Form spec v1 endpoints: validate a document, dry-run edit operations.

Both need ``form.edit`` in the workspace (the form edit permission) and
store nothing. docs/spec/README.md describes the document."""

from typing import Any, Dict

from beanie import PydanticObjectId
from classy_fastapi import Routable, post
from common.models.user import User
from fastapi import Depends, Request

from backend.app.container import container
from backend.app.router import router
from backend.app.services.form_spec.service import DryRunRequest, DryRunResponse
from backend.app.services.user_service import get_logged_user


@router(prefix="/workspaces/{workspace_id}/forms", tags=["Form spec"])
class FormSpecRouter(Routable):
    @post(
        "/validate",
        # The body is read by hand (size-capped), so describe it here.
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": {"type": "object"}}},
            }
        },
        responses={
            413: {"description": "The document is larger than 1 MB."},
            422: {"description": "The body is not valid JSON."},
        },
    )
    async def validate_form_spec(
        self,
        workspace_id: PydanticObjectId,
        request: Request,
        user: User = Depends(get_logged_user),
    ) -> Dict[str, Any]:
        """Check a form spec document (the JSON body, at most 1 MB):
        ``{valid, errors: [{path, message}], warnings, compliance}``. Never
        stores anything."""
        return await container.form_spec_service().validate_request(
            workspace_id=workspace_id, request=request, user=user
        )

    @post("/{form_id}/ops/dry-run", response_model=DryRunResponse)
    async def dry_run_form_ops(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        request: DryRunRequest,
        user: User = Depends(get_logged_user),
    ) -> DryRunResponse:
        """What the operations would make of the form: the resulting spec
        document, a diff and per-operation results. Never stores anything."""
        return await container.form_spec_service().dry_run(
            workspace_id=workspace_id, form_id=form_id, request=request, user=user
        )
