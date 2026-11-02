"""The switch of the audit log pages, ``AUDIT_LOG_UI_ENABLED`` (default off until
it is released).

Off: the two read routes answer 422 ``audit_log_off`` before anything is read
(no query, no permission lookup) and the dashboard shows no Activity page. The
events themselves are written either way: this switch never gates a writer.
"""

from http import HTTPStatus

from backend.app.exceptions import HTTPException
from backend.config import settings

OFF_CODE = "audit_log_off"
OFF_MESSAGE = (
    "The audit log is not switched on on this server yet "
    "(AUDIT_LOG_UI_ENABLED is off)."
)


def audit_log_ui_enabled() -> bool:
    """Is ``AUDIT_LOG_UI_ENABLED`` on?"""
    return bool(getattr(settings, "AUDIT_LOG_UI_ENABLED", False))


def refuse_when_off() -> None:
    if not audit_log_ui_enabled():
        raise HTTPException(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            content={"code": OFF_CODE, "message": OFF_MESSAGE},
        )
