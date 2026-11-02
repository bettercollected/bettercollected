"""The server switch of the versions page, ``FORM_REVISIONS_UI_ENABLED``
(default off until it is released).

Off: listing a form's published versions, comparing two of them and restoring
one into the draft are refused (422 ``form_revisions_disabled``) and the
dashboard does not show the Versions page. Reading one version
(``GET .../versions/{version}``) is not part of the switch: respondents and the
responses table use it.
"""

from http import HTTPStatus

from backend.app.exceptions import HTTPException

DISABLED_CODE = "form_revisions_disabled"
DISABLED_MESSAGE = (
    "The versions page is not switched on on this server yet "
    "(FORM_REVISIONS_UI_ENABLED is off)."
)


def form_revisions_ui_enabled() -> bool:
    """Is ``FORM_REVISIONS_UI_ENABLED`` on?"""
    from backend.config import settings

    return bool(getattr(settings, "FORM_REVISIONS_UI_ENABLED", False))


def ensure_enabled() -> None:
    if not form_revisions_ui_enabled():
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={"code": DISABLED_CODE, "message": DISABLED_MESSAGE},
        )
