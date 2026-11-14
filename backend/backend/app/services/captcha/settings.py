"""The automatic spam check as a workspace setting, and its counts.

``captcha_default`` on the workspace document says whether the workspace's forms
ask for the check unless a form's own setting says otherwise (not chosen: yes).
Changing it needs ``workspace.manage``, is recorded in the workspace's audit log
(``captcha_setting_changed``, who and the new value, written first or the change
is refused) and, like the per-form setting, needs the server switch
``CAPTCHA_ENABLED``: while it is off, reading answers 404 ``captcha_off`` and a
change answers 422 ``captcha_disabled`` (a stored value is kept, neither enforced
nor shown).

The counts (``stats.py``) are numbers by day for a workspace or a form, never a
person: a workspace's for ``workspace.manage``, a form's for ``analytics.read``
on that form.
"""

from typing import Optional

from common.ids import RecordId
from common.models.user import User
from fastapi_camelcase import CamelModel

from backend.app.models.enum.permission import Permission
from backend.app.schemas.workspace_audit_event import CAPTCHA_SETTING_CHANGED
from backend.app.services.captcha import mode
from backend.app.services.captcha.stats import CaptchaStats
from backend.app.services.form_access import audit


class CaptchaSettingsDto(CamelModel):
    # whether the workspace's forms ask for the check unless one says otherwise
    captcha_default: bool
    can_manage: bool = True


class SetCaptchaDefaultDto(CamelModel):
    captcha_default: bool


class CaptchaSettingsService:
    def __init__(
        self,
        workspace_repo,
        authorization_service,
        stats: CaptchaStats,
        audit_repo=None,
    ):
        self._workspaces = workspace_repo
        self._authorization = authorization_service
        self._stats = stats
        self._audit_repo = audit_repo

    async def get(self, workspace_id: RecordId, user: User) -> CaptchaSettingsDto:
        await self._authorization.authorize(
            user, Permission.WORKSPACE_MANAGE, workspace_id
        )
        if not mode.captcha_enabled():
            raise mode.off_error()
        workspace = await self._workspaces.get_or_404(workspace_id)
        return CaptchaSettingsDto(captcha_default=workspace.captcha_default is not False)

    async def set_default(
        self, workspace_id: RecordId, user: User, value: bool
    ) -> CaptchaSettingsDto:
        await self._authorization.authorize(
            user, Permission.WORKSPACE_MANAGE, workspace_id
        )
        workspace = await self._workspaces.get_or_404(workspace_id)
        mode.ensure_captcha_allowed(value, workspace.captcha_default)
        if workspace.captcha_default is not value:
            # recorded first, or refused: a change is never made unrecorded
            await audit.record_or_refuse(
                self._audit_repo,
                CAPTCHA_SETTING_CHANGED,
                workspace_id,
                user,
                enabled=value,
            )
            await self._workspaces.set_fields(workspace, {"captcha_default": value})
        return CaptchaSettingsDto(captcha_default=value)

    async def workspace_counts(self, workspace_id: RecordId, user: User) -> dict:
        """The last 30 days of the whole workspace (``workspace.manage``)."""
        await self._authorization.authorize(
            user, Permission.WORKSPACE_MANAGE, workspace_id
        )
        if not mode.captcha_enabled():
            raise mode.off_error()
        return await self._stats.summary(workspace_id=str(workspace_id))

    async def form_counts(
        self, workspace_id: RecordId, form_id: str, user: User
    ) -> dict:
        """The last 30 days of one form (``analytics.read`` on that form: a form
        closed to the caller, or of another workspace, is a 404)."""
        await self._authorization.authorize(
            user, Permission.ANALYTICS_READ, workspace_id, form_id=str(form_id)
        )
        if not mode.captcha_enabled():
            raise mode.off_error()
        return await self._stats.summary(form_id=str(form_id))


async def record_form_setting_change(
    audit_repo, workspace_id, user, form_id, value: Optional[bool]
):
    """The audit call for a form's own setting changed from the settings PATCH
    (kept here with the other call of the event)."""
    await audit.record_or_refuse(
        audit_repo,
        CAPTCHA_SETTING_CHANGED,
        workspace_id,
        user,
        form_id=str(form_id),
        enabled=value,
    )
