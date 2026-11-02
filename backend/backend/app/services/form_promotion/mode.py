"""The switch of copying a form to another workspace, ``FORM_PROMOTION_ENABLED``
(default off until it is released).

Off: the promotion routes answer 422 ``form_promotion_disabled``, before the
body is read and before any query is made for the request. Nothing else is
gated: the public spec API, the SDK and the CLI are not part of the switch, a
``promotedFrom`` mark that is already stored is kept, and respondents never see
it either way (``services/internal_fields.py``).
"""

from http import HTTPStatus

from backend.app.exceptions import HTTPException

DISABLED_CODE = "form_promotion_disabled"
DISABLED_MESSAGE = (
    "Copying a form to another workspace is not switched on on this server yet "
    "(FORM_PROMOTION_ENABLED is off)."
)


def form_promotion_enabled() -> bool:
    """Is ``FORM_PROMOTION_ENABLED`` on?"""
    from backend.config import settings

    return bool(settings.form_promotion.ENABLED)


def ensure_enabled() -> None:
    """422 ``form_promotion_disabled`` while the switch is off. Used as a route
    dependency, so it runs before the service is reached."""
    if not form_promotion_enabled():
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={"code": DISABLED_CODE, "message": DISABLED_MESSAGE},
        )
