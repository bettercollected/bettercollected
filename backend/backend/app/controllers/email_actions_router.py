from http import HTTPStatus
from typing import List, Optional

from classy_fastapi import Routable, delete, get, patch, post
from common.ids import RecordId
from common.models.user import User
from fastapi import Depends, Query, Response

from backend.app.container import container
from backend.app.router import router
from backend.app.services.email_actions.service import (
    DeliveryDto,
    DeliveryPageDto,
    EmailActionCreateDto,
    EmailActionDto,
    EmailActionUpdateDto,
    PreviewDto,
    PreviewRequestDto,
    StatusDto,
    TestRequestDto,
)
from backend.app.services.user_service import get_full_user
from backend.app.services.webhooks.service import VariableDto


@router(
    prefix="/workspaces",
    tags=["Email actions"],
    responses={
        401: {"description": "Authorization token is missing."},
        403: {"description": "The caller lacks the permission."},
    },
)
class EmailActionsRouter(Routable):
    """Mailing a form's submissions to the form's team, and a copy to the
    respondent (docs/email-actions.md). Owners and admins configure; whoever
    edits the form or reads the audit log sees the delivery log. No endpoint
    mails an address the caller supplies: a test mail goes to the caller."""

    @get("/{workspace_id}/email-actions/status")
    async def email_actions_status(
        self, workspace_id: RecordId, user: User = Depends(get_full_user)
    ) -> StatusDto:
        from backend.app.models.enum.permission import Permission

        await container.authorization_service().authorize(
            user, Permission.FORM_READ, workspace_id
        )
        return container.email_action_service().status()

    @get("/{workspace_id}/forms/{form_id}/email-actions")
    async def list_email_actions(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: User = Depends(get_full_user),
    ) -> List[EmailActionDto]:
        return await container.email_action_service().list_actions(
            workspace_id, form_id, user
        )

    @get("/{workspace_id}/forms/{form_id}/email-actions/variables")
    async def list_email_variables(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: User = Depends(get_full_user),
    ) -> List[VariableDto]:
        return await container.email_action_service().list_variables(
            workspace_id, form_id, user
        )

    @post(
        "/{workspace_id}/forms/{form_id}/email-actions",
        status_code=HTTPStatus.CREATED,
        responses={
            422: {
                "description": "email_actions_off, mail_not_configured, "
                "recipient_not_allowed, unknown_placeholder, invalid_condition, ..."
            },
        },
    )
    async def create_email_action(
        self,
        workspace_id: RecordId,
        form_id: str,
        request: EmailActionCreateDto,
        user: User = Depends(get_full_user),
    ) -> EmailActionDto:
        return await container.email_action_service().create_action(
            workspace_id, form_id, request, user
        )

    @post("/{workspace_id}/forms/{form_id}/email-actions/preview")
    async def preview_email(
        self,
        workspace_id: RecordId,
        form_id: str,
        request: PreviewRequestDto,
        user: User = Depends(get_full_user),
    ) -> PreviewDto:
        """A template rendered with made-up answers (nothing is sent)."""
        return await container.email_action_service().preview(
            workspace_id, form_id, request, user
        )

    @get("/{workspace_id}/forms/{form_id}/email-actions/deliveries")
    async def list_email_deliveries(
        self,
        workspace_id: RecordId,
        form_id: str,
        status: Optional[List[str]] = Query(None),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        user: User = Depends(get_full_user),
    ) -> DeliveryPageDto:
        return await container.email_action_service().list_deliveries(
            workspace_id, form_id, user, statuses=status, limit=limit, offset=offset
        )

    @patch("/{workspace_id}/forms/{form_id}/email-actions/{action_id}")
    async def update_email_action(
        self,
        workspace_id: RecordId,
        form_id: str,
        action_id: str,
        request: EmailActionUpdateDto,
        user: User = Depends(get_full_user),
    ) -> EmailActionDto:
        return await container.email_action_service().update_action(
            workspace_id, form_id, action_id, request, user
        )

    @delete(
        "/{workspace_id}/forms/{form_id}/email-actions/{action_id}",
        status_code=HTTPStatus.NO_CONTENT,
    )
    async def delete_email_action(
        self,
        workspace_id: RecordId,
        form_id: str,
        action_id: str,
        user: User = Depends(get_full_user),
    ) -> Response:
        await container.email_action_service().delete_action(
            workspace_id, form_id, action_id, user
        )
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @post(
        "/{workspace_id}/forms/{form_id}/email-actions/{action_id}/test",
        responses={429: {"description": "Too many test mails (rate_limited)."}},
    )
    async def send_email_test(
        self,
        workspace_id: RecordId,
        form_id: str,
        action_id: str,
        request: Optional[TestRequestDto] = None,
        user: User = Depends(get_full_user),
    ) -> DeliveryDto:
        """Send the action's mail, with made-up answers, to the caller's own
        address and nobody else."""
        return await container.email_action_service().send_test(
            workspace_id, form_id, action_id, request or TestRequestDto(), user
        )
