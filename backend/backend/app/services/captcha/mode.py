"""The server switch of the proof of work, ``CAPTCHA_ENABLED`` (default off
until it is released).

Off means all of these: the challenge route answers 404 before it looks at
anything; the ``X-BC-Captcha`` header is never read (no verification, no
claim, no counter, no refusal for a missing or garbage header); respondents are
served forms without the setting; creators cannot change the per-form setting
(422 ``captcha_disabled`` on every write path: settings PATCH, form spec API,
operations, which the AI and MCP use too); nothing is recorded. A stored value
is kept, neither enforced nor shown.
"""

from http import HTTPStatus
from typing import Optional

from backend.app.exceptions import HTTPException

DISABLED_CODE = "captcha_disabled"
DISABLED_MESSAGE = (
    "The automatic spam check is not switched on on this server yet "
    "(CAPTCHA_ENABLED is off)."
)
OFF_CODE = "captcha_off"


def captcha_enabled() -> bool:
    """Is ``CAPTCHA_ENABLED`` on?"""
    from backend.config import settings

    return bool(getattr(settings, "CAPTCHA_ENABLED", False))


def disabled_error() -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content={"code": DISABLED_CODE, "message": DISABLED_MESSAGE},
    )


def off_error() -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.NOT_FOUND,
        content={"code": OFF_CODE, "message": "Not found."},
    )


def refuses(new_value: Optional[bool], current: Optional[bool] = None) -> bool:
    """Would a write of ``new_value`` over ``current`` be refused? Only while
    the switch is off, and only a write that sets the per-form setting to
    anything but what it already is: a form that has a value keeps it, and a
    save that leaves it as it is passes. The one rule every write path uses."""
    return new_value is not None and new_value != current and not captcha_enabled()


def ensure_captcha_allowed(
    new_value: Optional[bool], current: Optional[bool] = None
) -> None:
    """422 ``captcha_disabled`` when ``refuses(new_value, current)``."""
    if refuses(new_value, current):
        raise disabled_error()


def required_by(settings, workspace_default: Optional[bool] = None) -> bool:
    """Whether a form's settings ask for the check (switch on): the form's own
    choice, else the workspace's default (``captcha_default``), else on. Pure:
    the caller has checked the switch and read the workspace's default.
    ``settings`` is a model or a dict (snake_case or camelCase keys): the one
    rule the form page's ``captchaRequired`` and the submit's enforcement both
    use."""
    own = settings_own_value(settings)
    if own is not None:
        return own is not False
    return workspace_default is not False


def settings_own_value(settings) -> Optional[bool]:
    """The form's own ``captcha_enabled`` in a settings object or dict (a
    stored model or the camelCase document of a served form), None when the form
    follows the workspace's default."""
    if settings is None:
        return None
    if isinstance(settings, dict):
        value = settings.get("captcha_enabled")
        return value if value is not None else settings.get("captchaEnabled")
    return getattr(settings, "captcha_enabled", None)


async def workspace_default(workspace_id) -> Optional[bool]:
    """The workspace's ``captcha_default`` (None: the workspace has not chosen,
    which means on), or None for a workspace that cannot be read. One read of
    the workspace; call it only for a form that has no value of its own and only
    while the switch is on."""
    from backend.app.container import container

    workspace = await container.workspace_repo().find_by_id(workspace_id)
    return getattr(workspace, "captcha_default", None) if workspace else None


async def required_for(settings, workspace_id) -> bool:
    """``required_by`` for a form of ``workspace_id`` (switch on): the workspace
    is read only when the form has no value of its own."""
    own = settings_own_value(settings)
    return required_by(
        settings, await workspace_default(workspace_id) if own is None else None
    )


async def apply_workspace_default(form, workspace_id) -> None:
    """Respondent path, switch on: a form with no value of its own takes the
    workspace's default as its own in this copy of the settings, so the one
    serving rule (``required_by`` in ``internal_fields``) answers for the
    workspace's choice too. ``form`` is the served form, a dict or a model.
    Nothing when the form has a value, or the workspace has not chosen."""
    if not captcha_enabled():
        return
    settings = form.get("settings") if isinstance(form, dict) else getattr(form, "settings", None)
    if settings is None or settings_own_value(settings) is not None:
        return
    default = await workspace_default(workspace_id)
    if default is None:
        return
    if isinstance(settings, dict):
        settings["captcha_enabled"] = default
    else:
        settings.captcha_enabled = default


async def mark_required_for_staff(form, workspace_id) -> None:
    """``captcha_required`` on a published form served on the staff path (a
    member answering their own form is asked for the proof like anyone), with
    the workspace's default behind the form's own value. The creator's own
    setting stays as stored. Nothing while the switch is off."""
    if not captcha_enabled():
        return
    settings = form.get("settings") if isinstance(form, dict) else getattr(form, "settings", None)
    if settings is None:
        return
    key = "captcha_required"
    current = settings.get(key) if isinstance(settings, dict) else getattr(settings, key, None)
    if current is not None:
        return
    required = await required_for(settings, workspace_id)
    if isinstance(settings, dict):
        settings[key] = required
    elif hasattr(settings, key):
        setattr(settings, key, required)
