"""What the form-level access switch (``FORM_ACCESS_ENABLED``) allows.

On: grants, teams and restricted forms are enforced by the permission
decision for every request that names a form. Off (the default): none of it
is enforced and no decision reads the tables behind it: a member's permissions
on a form are those of their workspace role, exactly as before; the routes that
change teams, grants or a form's mode answer 422 ``form_access_off``. Saved
grants, teams and modes stay as they are. Read at call time from
``settings.form_access.ENABLED``.
"""

from http import HTTPStatus

from backend.app.exceptions import HTTPException
from backend.config import settings

OFF_CODE = "form_access_off"
OFF_MESSAGE = "Form-level access is turned off on this instance."


def form_access_enabled() -> bool:
    return bool(settings.form_access.ENABLED)


def refuse_when_off() -> None:
    if not form_access_enabled():
        raise HTTPException(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            content={"code": OFF_CODE, "message": OFF_MESSAGE},
        )
