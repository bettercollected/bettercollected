from http import HTTPStatus
from typing import List, Optional

from classy_fastapi import Routable, delete, get, patch, post
from common.ids import RecordId
from common.models.user import User
from fastapi import Depends, Query, Response

from backend.app.container import container
from backend.app.router import router
from backend.app.services.user_service import get_full_user
from backend.app.services.webhooks.service import (
    AuditDto,
    DeliveryDto,
    DeliveryPageDto,
    StatusDto,
    VariableDto,
    WebhookCreatedDto,
    WebhookCreateDto,
    WebhookDetailDto,
    WebhookDto,
    WebhookUpdateDto,
)


@router(
    prefix="/workspaces",
    tags=["Webhooks"],
    responses={
        401: {"description": "Authorization token is missing."},
        403: {"description": "The caller lacks the permission."},
    },
)
class WebhooksRouter(Routable):
    """Sending a form's submissions to an https address of the workspace's own
    (docs/webhooks.md). Owners and admins configure; whoever edits the form or
    reads the audit log sees the delivery log. The signing secret is shown
    once, when it is created or rotated: no other response carries one."""

    @get("/{workspace_id}/webhooks/status")
    async def webhooks_status(
        self, workspace_id: RecordId, user: User = Depends(get_full_user)
    ) -> StatusDto:
        from backend.app.models.enum.permission import Permission

        await container.authorization_service().authorize(
            user, Permission.FORM_READ, workspace_id
        )
        return container.webhook_service().status()

    @get("/{workspace_id}/forms/{form_id}/webhooks")
    async def list_webhooks(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: User = Depends(get_full_user),
    ) -> List[WebhookDto]:
        return await container.webhook_service().list_webhooks(
            workspace_id, form_id, user
        )

    @get("/{workspace_id}/forms/{form_id}/webhooks/variables")
    async def list_variables(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: User = Depends(get_full_user),
    ) -> List[VariableDto]:
        return await container.webhook_service().list_variables(
            workspace_id, form_id, user
        )

    @post(
        "/{workspace_id}/forms/{form_id}/webhooks",
        status_code=HTTPStatus.CREATED,
        responses={
            422: {
                "description": "webhooks_off, invalid_url, not_https, not_allowed, "
                "unreachable, invalid_key, too_many_webhooks, ..."
            },
        },
    )
    async def create_webhook(
        self,
        workspace_id: RecordId,
        form_id: str,
        request: WebhookCreateDto,
        user: User = Depends(get_full_user),
    ) -> WebhookCreatedDto:
        return await container.webhook_service().create_webhook(
            workspace_id, form_id, request, user
        )

    @patch("/{workspace_id}/forms/{form_id}/webhooks/{webhook_id}")
    async def update_webhook(
        self,
        workspace_id: RecordId,
        form_id: str,
        webhook_id: str,
        request: WebhookUpdateDto,
        user: User = Depends(get_full_user),
    ) -> WebhookDto:
        return await container.webhook_service().update_webhook(
            workspace_id, form_id, webhook_id, request, user
        )

    @delete(
        "/{workspace_id}/forms/{form_id}/webhooks/{webhook_id}",
        status_code=HTTPStatus.NO_CONTENT,
    )
    async def delete_webhook(
        self,
        workspace_id: RecordId,
        form_id: str,
        webhook_id: str,
        user: User = Depends(get_full_user),
    ) -> Response:
        await container.webhook_service().delete_webhook(
            workspace_id, form_id, webhook_id, user
        )
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @post("/{workspace_id}/forms/{form_id}/webhooks/{webhook_id}/rotate-secret")
    async def rotate_secret(
        self,
        workspace_id: RecordId,
        form_id: str,
        webhook_id: str,
        user: User = Depends(get_full_user),
    ) -> WebhookCreatedDto:
        return await container.webhook_service().rotate_secret(
            workspace_id, form_id, webhook_id, user
        )

    @post(
        "/{workspace_id}/forms/{form_id}/webhooks/{webhook_id}/test",
        responses={429: {"description": "Too many test events (rate_limited)."}},
    )
    async def send_test(
        self,
        workspace_id: RecordId,
        form_id: str,
        webhook_id: str,
        user: User = Depends(get_full_user),
    ) -> DeliveryDto:
        """Queue a real, signed delivery of made-up data for the mapped
        questions; its outcome shows in the deliveries."""
        return await container.webhook_service().send_test(
            workspace_id, form_id, webhook_id, user
        )

    @get("/{workspace_id}/forms/{form_id}/webhooks/deliveries")
    async def list_deliveries(
        self,
        workspace_id: RecordId,
        form_id: str,
        status: Optional[List[str]] = Query(None),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        user: User = Depends(get_full_user),
    ) -> DeliveryPageDto:
        return await container.webhook_service().list_deliveries(
            workspace_id, form_id, user, statuses=status, limit=limit, offset=offset
        )

    @get("/{workspace_id}/forms/{form_id}/webhooks/audit")
    async def list_audit(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: User = Depends(get_full_user),
    ) -> List[AuditDto]:
        return await container.webhook_service().list_audit(
            workspace_id, form_id, user
        )

    @get("/{workspace_id}/forms/{form_id}/webhooks/{webhook_id}/detail")
    async def get_webhook(
        self,
        workspace_id: RecordId,
        form_id: str,
        webhook_id: str,
        user: User = Depends(get_full_user),
    ) -> WebhookDetailDto:
        """The owner-facing view of one webhook, with its address (to edit it)."""
        return await container.webhook_service().get_webhook(
            workspace_id, form_id, webhook_id, user
        )
