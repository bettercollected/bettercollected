"""The switch of the second app theme, ``APP_THEME_PIGMENT_ENABLED`` (default off
until it is released).

Off means all of these: choosing ``pigment`` answers 422 ``app_theme_disabled``
(``daybreak`` is never refused: it is a change, stored and recorded, when the
workspace has ``pigment`` stored, and no change when it has nothing or
``daybreak`` stored); a stored ``pigment`` is kept until then, but the workspace
is served ``daybreak`` (``effective_theme``); the permissions answer says
``appThemeEnabled: false``. Nothing else is gated.
"""

from http import HTTPStatus
from typing import Optional

from backend.app.exceptions import HTTPException
from backend.app.models.workspace import AppTheme

DISABLED_CODE = "app_theme_disabled"
DISABLED_MESSAGE = (
    "The Pigment theme is not switched on on this server yet "
    "(APP_THEME_PIGMENT_ENABLED is off)."
)
DEFAULT_THEME: AppTheme = "daybreak"


def app_theme_pigment_enabled() -> bool:
    """Is ``APP_THEME_PIGMENT_ENABLED`` on?"""
    from backend.config import settings

    return bool(settings.app_theme.ENABLED)


def effective_theme(stored: Optional[str]) -> AppTheme:
    """The theme a workspace is served: what it stored, ``daybreak`` when it
    stored nothing, and ``daybreak`` whatever it stored while the switch is
    off."""
    if stored == "pigment" and app_theme_pigment_enabled():
        return "pigment"
    return DEFAULT_THEME


def disabled_error() -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content={"code": DISABLED_CODE, "message": DISABLED_MESSAGE},
    )


def ensure_choice_allowed(value: str) -> None:
    """422 ``app_theme_disabled`` for a choice of ``pigment`` while the switch
    is off (that is always a change: the workspace is served ``daybreak``)."""
    if value != DEFAULT_THEME and not app_theme_pigment_enabled():
        raise disabled_error()
