from common.models.user import User
from backend.app.services.workspace_user_service import WorkspaceUserService


class AnalyticsService:
    def __init__(
        self,
        workspace_user_service: WorkspaceUserService,
    ):
        self.workspace_user_service = workspace_user_service

    async def check_user_can_view_analytics(self, workspace_name: str, user: User):
        await self.workspace_user_service.check_user_has_access_by_workspace_name(
            workspace_name=workspace_name, user=user
        )
