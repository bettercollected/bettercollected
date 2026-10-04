from common.models.user import User

from backend.app.models.enum.permission import Permission
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.services.authorization_service import AuthorizationService


class AnalyticsService:
    def __init__(
        self,
        authorization_service: AuthorizationService,
        workspace_repo: WorkspaceRepository,
    ):
        self._authorization = authorization_service
        self._workspace_repo = workspace_repo

    async def check_user_can_view_analytics(self, workspace_name: str, user: User):
        workspace = await self._workspace_repo.find_by_name(workspace_name)
        await self._authorization.authorize(
            user, Permission.ANALYTICS_READ, workspace.id if workspace else None
        )
