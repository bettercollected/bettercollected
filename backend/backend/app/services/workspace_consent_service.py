from beanie import PydanticObjectId

from backend.app.models.dtos.consent import ConsentCamelModel
from backend.app.repositories.workspace_consent_repo import WorkspaceConsentRepo
from backend.app.services.authorization_service import AuthorizationService
from backend.app.models.enum.permission import Permission
from common.models.user import User


class WorkspaceConsentService:
    def __init__(
        self,
        workspace_consent_repo: WorkspaceConsentRepo,
        authorization_service: AuthorizationService,
    ):
        self._workspace_consent_repo: WorkspaceConsentRepo = workspace_consent_repo
        self._authorization = authorization_service

    async def get_workspace_consents(self, workspace_id: PydanticObjectId, user: User):
        await self._authorization.authorize(user, Permission.FORM_EDIT, workspace_id)
        return await self._workspace_consent_repo.get_workspace_consents(
            workspace_id=workspace_id
        )

    async def create_workspace_consent(
        self, workspace_id: PydanticObjectId, consent: ConsentCamelModel, user: User
    ):
        await self._authorization.authorize(
            user, Permission.PRIVACY_MANAGE, workspace_id
        )
        return await self._workspace_consent_repo.create_workspace_consent(
            workspace_id=workspace_id, consent=consent
        )
