"""Platform admins named by configuration (``PLATFORM_ADMIN_EMAILS``).

A listed email gets the ADMIN role, and with it every platform-admin power
(``get_logged_admin`` in the backend), not only the metrics page. So the grant
needs proof the user owns the address: it applies only to sessions whose email
was verified at sign-in (OTP, or Google reporting it verified), never to a
provider that merely returns an email (Typeform) or to an unverified one.

The role is added when roles go into a token (login, and ``/auth/status``,
which the backend refreshes access tokens from, told whether the session was
verified), never stored. Removing an email therefore revokes the role at that
user's next token; tokens already issued keep it until they expire
(``AUTH_ACCESS_TOKEN_EXPIRY_IN_MINUTES``). An ADMIN stored on the user document
still counts as before.
"""

from typing import Iterable, List, Optional

from common.enums.roles import Roles

from auth.config import settings


def platform_admin_emails(configured: Optional[str] = None) -> frozenset:
    raw = settings.PLATFORM_ADMIN_EMAILS if configured is None else configured
    return frozenset(
        email.strip().lower() for email in (raw or "").split(",") if email.strip()
    )


def roles_for(
    email: Optional[str],
    roles: Optional[Iterable[str]],
    verified: bool,
    configured: Optional[str] = None,
) -> List[str]:
    """``roles`` plus ADMIN when ``email`` is a configured platform admin and
    was verified at sign-in; otherwise ``roles`` unchanged."""
    effective = list(roles or [])
    if (
        verified is True
        and email
        and email.strip().lower() in platform_admin_emails(configured)
        and Roles.ADMIN not in effective
    ):
        effective.append(Roles.ADMIN.value)
    return effective
