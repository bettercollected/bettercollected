from beanie import PydanticObjectId

from backend.app.models.dtos.consent import ConsentCamelModel
from backend.app.repositories.workspace_consent_repo import WorkspaceConsentRepo
from backend.app.services.workspace_user_service import WorkspaceUserService
from common.models.user import User


class WorkspaceConsentService:

    def __init__(self, workspace_consent_repo: WorkspaceConsentRepo, workspace_user_service: WorkspaceUserService):
        self._workspace_consent_repo: WorkspaceConsentRepo = workspace_consent_repo
        self._workspace_user_service: WorkspaceUserService = workspace_user_service

    async def get_workspace_consents(self, workspace_id: PydanticObjectId, user: User):
        await self._workspace_user_service.check_user_has_access_in_workspace(workspace_id=workspace_id, user=user)
        return await self._workspace_consent_repo.get_workspace_consents(workspace_id=workspace_id)

    async def create_workspace_consent(self, workspace_id: PydanticObjectId, consent: ConsentCamelModel, user: User):
        await self._workspace_user_service.check_user_has_access_in_workspace(workspace_id=workspace_id, user=user)
        return await self._workspace_consent_repo.create_workspace_consent(workspace_id=workspace_id, consent=consent)
