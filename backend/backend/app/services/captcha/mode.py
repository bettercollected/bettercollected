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


def required_by(settings) -> bool:
    """Whether a form's settings ask for the check (switch on): the form's own
    choice, else on. Pure: the caller has checked the switch. ``settings`` is
    a model or a dict (snake_case or camelCase keys): the one rule the form
    page's ``captchaRequired`` and the submit's enforcement both use."""
    if isinstance(settings, dict):
        stored = settings.get("captcha_enabled")
        if stored is None:
            stored = settings.get("captchaEnabled")
    else:
        stored = getattr(settings, "captcha_enabled", None)
    return stored is not False
