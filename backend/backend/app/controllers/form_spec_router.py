"""Form spec v1 endpoints: validate a document, dry-run edit operations,
and the builder's op-batch save.

All need ``form.edit`` in the workspace (the form edit permission); only the
save stores anything. docs/spec/README.md describes the document."""

from typing import Any, Dict, Optional

from common.ids import RecordId
from classy_fastapi import Routable, post
from common.models.user import User
from fastapi import Depends, Header, Request
from pydantic import BaseModel, Field

from backend.app.container import container
from backend.app.router import router
from backend.app.services.form_spec.service import DryRunRequest, DryRunResponse
from backend.app.services.user_service import get_logged_user


class PatternCheckRequest(BaseModel):
    pattern: str = Field(max_length=1000)


class PatternCheckResponse(BaseModel):
    valid: bool
    message: Optional[str] = None
    reason: Optional[str] = None


@router(prefix="/workspaces/{workspace_id}/forms", tags=["Form spec"])
class FormSpecRouter(Routable):
    @post("/pattern/check", response_model=PatternCheckResponse)
    async def check_answer_pattern(
        self,
        workspace_id: RecordId,
        request: PatternCheckRequest,
        user: User = Depends(get_logged_user),
    ) -> PatternCheckResponse:
        """Whether an answer pattern can be saved (RE2 syntax, at most 200
        characters): ``{valid, message}``. The builder asks while a pattern
        is typed. Needs ``form.edit``; stores nothing."""
        return await container.form_spec_service().check_pattern(
            workspace_id=workspace_id, pattern=request.pattern, user=user
        )

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
        workspace_id: RecordId,
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
        workspace_id: RecordId,
        form_id: str,
        request: DryRunRequest,
        user: User = Depends(get_logged_user),
    ) -> DryRunResponse:
        """What the operations would make of the form: the resulting spec
        document, a diff and per-operation results. Never stores anything."""
        return await container.form_spec_service().dry_run(
            workspace_id=workspace_id, form_id=form_id, request=request, user=user
        )

    @post(
        "/{form_id}/ops",
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["ops"],
                            "properties": {
                                "ops": {"type": "array", "items": {"type": "object"}},
                                "atomic": {"type": "boolean", "enum": [True]},
                            },
                        }
                    }
                },
            }
        },
        responses={
            400: {"description": "No (or an invalid) Idempotency-Key."},
            404: {"description": "No such form, or op saves are not enabled."},
            409: {"description": "A request with this Idempotency-Key still runs."},
            412: {"description": "The form changed since the ETag in If-Match."},
            413: {"description": "The body is larger than 1 MB."},
            422: {"description": "Invalid operations, or one failed (nothing stored)."},
            428: {"description": "If-Match is required."},
        },
    )
    async def save_form_ops(
        self,
        workspace_id: RecordId,
        form_id: str,
        request: Request,
        if_match: Optional[str] = Header(None, alias="If-Match"),
        idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
        user: User = Depends(get_logged_user),
    ):
        """Save a batch of edits to the draft as operations, all or nothing,
        only while it is still the version ``If-Match`` names. Answers the
        form as the editor's GET serves it, its new ``ETag`` (header and
        ``etag``) and per-operation results."""
        return await container.editor_ops_service().save(
            workspace_id=workspace_id,
            form_id=form_id,
            request=request,
            user=user,
            if_match=if_match,
            idempotency_key=idempotency_key,
        )
