from http import HTTPStatus
from typing import Optional

from common.models.user import User

from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.repositories.postgres.forms import PostgresWorkspaceFormRepository
from backend.app.repositories.postgres.identity import PostgresWorkspaceRepository
from backend.app.services.authorization_service import AuthorizationService
from backend.app.services.form_access.mode import form_access_enabled


class AnalyticsService:
    def __init__(
        self,
        authorization_service: AuthorizationService,
        workspace_repo: PostgresWorkspaceRepository,
        workspace_form_repo: Optional[PostgresWorkspaceFormRepository] = None,
    ):
        self._authorization = authorization_service
        self._workspace_repo = workspace_repo
        self._workspace_form_repo = workspace_form_repo

    async def check_user_can_view_analytics(
        self, workspace_name: str, user: User, slug: Optional[str] = None
    ):
        """403 without ``analytics.read``; with ``slug`` (the form's id or custom
        URL, which is what the visits are recorded under) and form-level access
        on, also 404 for a form that is not the workspace's or that a
        restricted form is closed to the member: the same answer for both."""
        workspace = await self._workspace_repo.find_by_name(workspace_name)
        workspace_id = workspace.id if workspace else None
        await self._authorization.authorize(
            user, Permission.ANALYTICS_READ, workspace_id
        )
        if (
            slug is None
            or not form_access_enabled()
            or self._workspace_form_repo is None
        ):
            return
        link = await self._workspace_form_repo.get_workspace_form_in_workspace(
            workspace_id, slug
        )
        if link is None:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Form not found in workspace")
        await self._authorization.authorize(
            user, Permission.ANALYTICS_READ, workspace_id, form_id=str(link.form_id)
        )
