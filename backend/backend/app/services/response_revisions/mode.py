"""The server switch of staff edit and the revision log,
``RESPONSE_REVISIONS_ENABLED`` (default off until it is released).

Off: a staff edit of answers and the history of a response are refused (422
``response_revisions_disabled``) and **nothing is recorded**, not even for a
respondent's own edit: the product behaves as before. Entries already stored
stay (and are erased with their response, whatever the switch says).
"""

from http import HTTPStatus

from backend.app.exceptions import HTTPException

DISABLED_CODE = "response_revisions_disabled"
DISABLED_MESSAGE = (
    "Editing answers and their history are not switched on on this server yet "
    "(RESPONSE_REVISIONS_ENABLED is off)."
)


def response_revisions_enabled() -> bool:
    """Is ``RESPONSE_REVISIONS_ENABLED`` on?"""
    from backend.config import settings

    return bool(getattr(settings, "RESPONSE_REVISIONS_ENABLED", False))


def ensure_enabled() -> None:
    if not response_revisions_enabled():
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={"code": DISABLED_CODE, "message": DISABLED_MESSAGE},
        )
