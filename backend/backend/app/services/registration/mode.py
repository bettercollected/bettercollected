"""What the registration switch (``OPEN_FORMULIEREN_REGISTRATION``) allows.

``on``: everything. ``off`` (the default): every registration endpoint answers
410 ``registration_off`` (except the status read, which says so), nothing is
queued on submit, the jobs do nothing and the respondent's form names no
destination. Saved configuration and delivery records stay as they are. Read
at call time from ``settings.registration.REGISTRATION``.
"""

from http import HTTPStatus

from backend.app.exceptions import HTTPException
from backend.config import settings

OFF_CODE = "registration_off"
OFF_MESSAGE = "Registration of submissions is turned off on this instance."


def registration_enabled() -> bool:
    return settings.registration.REGISTRATION == "on"


def refuse_when_off() -> None:
    if not registration_enabled():
        raise HTTPException(
            HTTPStatus.GONE, content={"code": OFF_CODE, "message": OFF_MESSAGE}
        )
