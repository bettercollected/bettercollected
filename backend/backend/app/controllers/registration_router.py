from http import HTTPStatus
from typing import List, Optional

from classy_fastapi import Routable, delete, get, patch, post, put
from common.ids import RecordId
from common.models.user import User
from fastapi import Depends, Query, Response

from backend.app.container import container
from backend.app.models.enum.permission import Permission
from backend.app.router import router
from backend.app.services.registration.service import (
    DeliveryDto,
    DeliveryPageDto,
    FormRegistrationDto,
    FormRegistrationUpdateDto,
    ServiceCreateDto,
    ServiceDto,
    ServiceTestDto,
    ServiceUpdateDto,
    StatusDto,
    VariableDto,
)
from backend.app.services.user_service import get_full_user


@router(
    prefix="/workspaces",
    tags=["Registration"],
    responses={
        401: {"description": "Authorization token is missing."},
        403: {"description": "The caller lacks the permission."},
        410: {"description": "Registration is turned off (registration_off)."},
    },
)
class RegistrationRouter(Routable):
    """Sending a form's submissions to a workspace's case system
    (docs/open-formulieren-registration.md). Services and the choice of
    variables are for owners and admins; a failed delivery can be retried by
    editors. Secrets are write-only: no response carries one."""

    @get("/{workspace_id}/registration/status")
    async def registration_status(
        self, workspace_id: RecordId, user: User = Depends(get_full_user)
    ) -> StatusDto:
        await container.authorization_service().authorize(
            user, Permission.FORM_READ, workspace_id
        )
        return container.registration_service().status()

    @get("/{workspace_id}/registration/services")
    async def list_services(
        self, workspace_id: RecordId, user: User = Depends(get_full_user)
    ) -> List[ServiceDto]:
        return await container.registration_service().list_services(workspace_id, user)

    @post(
        "/{workspace_id}/registration/services",
        status_code=HTTPStatus.CREATED,
        responses={
            409: {"description": "A service with this name exists (name_taken)."},
            422: {
                "description": "invalid_url, not_allowed, unreachable, secret_required, ..."
            },
        },
    )
    async def create_service(
        self,
        workspace_id: RecordId,
        request: ServiceCreateDto,
        user: User = Depends(get_full_user),
    ) -> ServiceDto:
        return await container.registration_service().create_service(
            workspace_id, request, user
        )

    @patch("/{workspace_id}/registration/services/{service_id}")
    async def update_service(
        self,
        workspace_id: RecordId,
        service_id: str,
        request: ServiceUpdateDto,
        user: User = Depends(get_full_user),
    ) -> ServiceDto:
        return await container.registration_service().update_service(
            workspace_id, service_id, request, user
        )

    @delete(
        "/{workspace_id}/registration/services/{service_id}",
        status_code=HTTPStatus.NO_CONTENT,
        responses={409: {"description": "A form still uses it (service_in_use)."}},
    )
    async def delete_service(
        self,
        workspace_id: RecordId,
        service_id: str,
        user: User = Depends(get_full_user),
    ) -> Response:
        await container.registration_service().delete_service(
            workspace_id, service_id, user
        )
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @post("/{workspace_id}/registration/services/{service_id}/test")
    async def test_service(
        self,
        workspace_id: RecordId,
        service_id: str,
        user: User = Depends(get_full_user),
    ) -> ServiceTestDto:
        return await container.registration_service().test_service(
            workspace_id, service_id, user
        )

    @get("/{workspace_id}/forms/{form_id}/registration")
    async def get_form_registration(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: User = Depends(get_full_user),
    ) -> FormRegistrationDto:
        return await container.registration_service().get_form_registration(
            workspace_id, form_id, user
        )

    @put("/{workspace_id}/forms/{form_id}/registration")
    async def put_form_registration(
        self,
        workspace_id: RecordId,
        form_id: str,
        request: FormRegistrationUpdateDto,
        user: User = Depends(get_full_user),
    ) -> FormRegistrationDto:
        return await container.registration_service().put_form_registration(
            workspace_id, form_id, request, user
        )

    @post("/{workspace_id}/forms/{form_id}/registration/test")
    async def check_connection(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: User = Depends(get_full_user),
    ) -> ServiceTestDto:
        """Objects API forms: look up a reference that cannot exist, with the
        saved settings. Reads no records; answers our code only."""
        return await container.registration_service().check_connection(
            workspace_id, form_id, user
        )

    @get("/{workspace_id}/forms/{form_id}/registration/variables")
    async def list_variables(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: User = Depends(get_full_user),
    ) -> List[VariableDto]:
        return await container.registration_service().list_variables(
            workspace_id, form_id, user
        )

    @get("/{workspace_id}/forms/{form_id}/registration/deliveries")
    async def list_deliveries(
        self,
        workspace_id: RecordId,
        form_id: str,
        status: Optional[List[str]] = Query(None),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        user: User = Depends(get_full_user),
    ) -> DeliveryPageDto:
        return await container.registration_service().list_deliveries(
            workspace_id,
            form_id,
            user,
            statuses=status,
            limit=limit,
            offset=offset,
        )

    @post(
        "/{workspace_id}/forms/{form_id}/registration/deliveries/{delivery_id}/retry",
        responses={409: {"description": "Not failed (not_retryable)."}},
    )
    async def retry_delivery(
        self,
        workspace_id: RecordId,
        form_id: str,
        delivery_id: str,
        user: User = Depends(get_full_user),
    ) -> DeliveryDto:
        return await container.registration_service().retry_delivery(
            workspace_id, form_id, delivery_id, user
        )
