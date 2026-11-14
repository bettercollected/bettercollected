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


def ensure_captcha_allowed(
    new_value: Optional[bool], current: Optional[bool] = None
) -> None:
    """While the switch is off, refuse (422 ``captcha_disabled``) a write that
    sets the per-form setting to anything but what it already is. A form that
    has a value keeps it: a save that leaves it as it is passes."""
    if new_value is not None and new_value != current and not captcha_enabled():
        raise disabled_error()


def required_by(settings) -> bool:
    """Whether a form's settings ask for the check (switch on): the form's own
    choice, else on. Pure: the caller has checked the switch."""
    return getattr(settings, "captcha_enabled", None) is not False
