"""What the key roles switch (``API_KEY_ROLES_ENABLED``) allows.

Off (the default): giving a key a role or a list of forms answers 422
``api_key_roles_off``; a key made without either behaves as it always has,
decided by the same code with no new query. A limit already stored on a key is
still enforced (setting is gated, enforcing is not: switching this off never
widens a key). Read at call time from ``settings.api_key_roles.ENABLED``.
"""

from http import HTTPStatus
from typing import Optional

from backend.app.exceptions import HTTPException
from backend.app.services.api_key_roles.model import SCOPE_ALL
from backend.config import settings

OFF_CODE = "api_key_roles_off"
OFF_MESSAGE = "API key roles are turned off on this instance."


def api_key_roles_enabled() -> bool:
    return bool(settings.api_key_roles.ENABLED)


def refuse_when_off() -> None:
    """422 ``api_key_roles_off`` while the switch is off: for a route that only
    exists to set a role or a form list (the key edit route)."""
    if not api_key_roles_enabled():
        raise HTTPException(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            content={"code": OFF_CODE, "message": OFF_MESSAGE},
        )


def refuse_setting_when_off(
    role: Optional[str] = None, form_scope: Optional[str] = None
) -> None:
    """422 ``api_key_roles_off`` when a request sets a role or a list of forms
    while the switch is off. A request that sets neither (or only the default
    scope, ``all``) is a key as it has always been, and goes through."""
    if role is None and form_scope in (None, SCOPE_ALL):
        return
    refuse_when_off()
