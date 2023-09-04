from typing import List

from beanie import PydanticObjectId
from classy_fastapi import Routable, get, post
from fastapi import Depends

from backend.app.container import container
from backend.app.models.dtos.consent import ConsentCamelModel
from backend.app.router import router
from backend.app.services.user_service import get_logged_user
from backend.app.services.workspace_consent_service import WorkspaceConsentService
from common.models.user import User


@router(prefix="/{workspace_id}/consent", tags=["Workspace Consent"])
class WorkspaceConsent(Routable):
    def __init__(
        self,
        workspace_consent_service: WorkspaceConsentService = container.workspace_consent_service(),
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.workspace_consent_service: WorkspaceConsentService = (
            workspace_consent_service
        )

    @get(
        "",
        response_model=List[ConsentCamelModel],
        responses={
            401: {"description": "Authorization token is missing."},
        },
    )
    async def get_workspace_consents(
        self, workspace_id: PydanticObjectId, user: User = Depends(get_logged_user)
    ):
        return await self.workspace_consent_service.get_workspace_consents(
            workspace_id=workspace_id, user=user
        )

    @post(
        "",
        response_model=ConsentCamelModel,
        responses={
            401: {"description": "Authorization token is missing."},
        },
    )
    async def create_workspace_consent(
        self,
        workspace_id: PydanticObjectId,
        consent: ConsentCamelModel,
        user: User = Depends(get_logged_user),
    ):
        return await self.workspace_consent_service.create_workspace_consent(
            workspace_id=workspace_id, consent=consent, user=user
        )
