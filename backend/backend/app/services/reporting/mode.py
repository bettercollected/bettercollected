"""The switch of reports on a form's answers, ``REPORTING_ENABLED`` (default off
until it is released).

Off: every report route answers 422 ``reporting_off`` as its first dependency,
before the body is read, before the session or any permission is looked at, and
before any row is read or decrypted. Nothing else is gated: the responses list,
the export, analytics and AI insights are exactly what they are with the switch
on. No audit event or stored row is written by a report either way.
"""

from http import HTTPStatus

from backend.app.exceptions import HTTPException

OFF_CODE = "reporting_off"
OFF_MESSAGE = (
    "Reports are not switched on on this server yet (REPORTING_ENABLED is off)."
)


def reporting_enabled() -> bool:
    """Is ``REPORTING_ENABLED`` on?"""
    from backend.config import settings

    return bool(settings.reporting.ENABLED)


def refuse_when_off() -> None:
    """422 ``reporting_off`` while the switch is off. Used as a route
    dependency, so it runs before the service is reached."""
    if not reporting_enabled():
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={"code": OFF_CODE, "message": OFF_MESSAGE},
        )
