"""The look of the staff dashboard as a workspace setting.

``app_theme`` on the workspace document is ``daybreak`` (the default) or
``pigment``. Changing it needs ``workspace.manage`` (Owner and Admin), is
recorded in the workspace's audit log (``app_theme_changed``: who, the theme now
and the one it replaced, written first or the change is refused) and, for
``pigment``, needs the server switch ``APP_THEME_PIGMENT_ENABLED``: while it is
off the change answers 422 ``app_theme_disabled`` (a stored value is kept,
neither enforced nor shown). Choosing the theme the workspace has stored (nothing
stored counts as ``daybreak``) is no change: nothing is refused, stored or recorded; ``daybreak`` is
never refused, even with the switch off.

The theme is served to members in the workspace answer for the dashboard
(``WorkspaceService.get_workspace_by_query``), never to a respondent.
"""

from common.ids import RecordId
from common.models.user import User
from fastapi_camelcase import CamelModel
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from backend.app.models.enum.permission import Permission
from backend.app.models.workspace import AppTheme
from backend.app.schemas.workspace_audit_event import APP_THEME_CHANGED
from backend.app.services.app_theme import mode
from backend.app.services.form_access import audit


class SetAppThemeDto(BaseModel):
    """``{"appTheme": "daybreak" | "pigment"}``, nothing else, nothing but those."""

    # the camelCase name only (what the docs say): `app_theme` in the body is a 422
    model_config = ConfigDict(alias_generator=to_camel, extra="forbid")

    app_theme: AppTheme


class AppThemeDto(CamelModel):
    # the theme the workspace is served now
    app_theme: AppTheme


class AppThemeService:
    def __init__(self, workspace_repo, authorization_service, audit_repo=None):
        self._workspaces = workspace_repo
        self._authorization = authorization_service
        self._audit_repo = audit_repo

    async def set_theme(
        self, workspace_id: RecordId, user: User, value: AppTheme
    ) -> AppThemeDto:
        await self._authorization.authorize(
            user, Permission.WORKSPACE_MANAGE, workspace_id
        )
        # a choice of pigment while the switch is off is always a change (the
        # workspace is served daybreak): refused before the workspace is read
        mode.ensure_choice_allowed(value)
        workspace = await self._workspaces.get_or_404(workspace_id)
        # what the workspace has *stored* (not chosen counts as daybreak), not what it
        # is served: with the switch off a stored pigment is served as daybreak, and an
        # admin who then chooses daybreak changes what comes back when it is turned on
        stored = workspace.app_theme or mode.DEFAULT_THEME
        if value == stored:
            # nothing to change, record or refuse
            return AppThemeDto(app_theme=value)
        # recorded first, or refused: a change is never made unrecorded
        await audit.record_or_refuse(
            self._audit_repo,
            APP_THEME_CHANGED,
            workspace_id,
            user,
            app_theme=value,
            previous_app_theme=stored,
        )
        await self._workspaces.set_fields(workspace, {"app_theme": value})
        return AppThemeDto(app_theme=value)
