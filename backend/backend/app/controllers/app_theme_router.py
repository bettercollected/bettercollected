"""The workspace's app theme (``services/app_theme``, ``APP_THEME_PIGMENT_ENABLED``):

* ``PUT /workspaces/{id}/app-theme``: choose ``daybreak`` or ``pigment``.

The theme is read from the workspace answer the dashboard already fetches
(members only), so there is no route to read it.
"""

from classy_fastapi import Routable, put
from common.ids import RecordId
from common.models.user import User
from fastapi import Depends

from backend.app.container import container
from backend.app.router import router
from backend.app.services.app_theme.service import AppThemeDto, SetAppThemeDto
from backend.app.services.user_service import get_logged_user


@router(
    prefix="/workspaces/{workspace_id}/app-theme",
    tags=["App theme"],
    responses={
        401: {"description": "Authorization token is missing."},
        403: {"description": "Needs workspace.manage (Owner or Admin)."},
        422: {"description": "Not a theme, or Pigment is not switched on."},
    },
)
class AppThemeRouter(Routable):
    @put("")
    async def set_app_theme(
        self,
        workspace_id: RecordId,
        body: SetAppThemeDto,
        user: User = Depends(get_logged_user),
    ) -> AppThemeDto:
        """Choose the workspace's app theme (``workspace.manage``; recorded in
        the audit log; 422 ``app_theme_disabled`` for ``pigment`` while the
        server switch is off)."""
        return await container.app_theme_service().set_theme(
            workspace_id, user, body.app_theme
        )
