"""The server switch of the drafts feature, ``SAVE_DRAFTS_ENABLED`` (default
off until it is released).

Off: turning a form's "save and continue later" setting on is refused (422
``save_drafts_disabled``) on every write path (settings PATCH, form spec API,
operations, which the AI and MCP use too), saving or opening a draft is refused
like a form that keeps none, respondents are served forms without the setting,
and the daily purge removes what drafts are left. Discarding a draft is always
allowed (erasure is never refused).
"""

from http import HTTPStatus
from typing import Optional

from backend.app.exceptions import HTTPException

DISABLED_CODE = "save_drafts_disabled"
DISABLED_MESSAGE = (
    "Saving drafts is not switched on on this server yet "
    "(SAVE_DRAFTS_ENABLED is off)."
)


def save_drafts_enabled() -> bool:
    """Is ``SAVE_DRAFTS_ENABLED`` on?"""
    from backend.config import settings

    return bool(getattr(settings, "SAVE_DRAFTS_ENABLED", False))


def disabled_error() -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content={"code": DISABLED_CODE, "message": DISABLED_MESSAGE},
    )


def ensure_save_drafts_allowed(
    turning_on: Optional[bool], currently_on: Optional[bool] = None
) -> None:
    """While the switch is off, refuse (422 ``save_drafts_disabled``) a write
    that turns the setting on. A form that already has it on keeps it (a save
    that leaves it as it is passes)."""
    if turning_on is True and not currently_on and not save_drafts_enabled():
        raise disabled_error()
