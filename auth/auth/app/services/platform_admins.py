"""Platform admins named by configuration (``PLATFORM_ADMIN_EMAILS``).

The ADMIN role is added when a user's roles go into a token (login, the
provider callbacks, and ``/auth/status``, which the backend refreshes access
tokens from), never stored. Removing an email from the setting therefore
revokes the role at that user's next token. An ADMIN stored on the user
document still counts as before.
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
    email: Optional[str], roles: Optional[Iterable[str]], configured=None
) -> List[str]:
    """``roles`` plus ADMIN when ``email`` is a configured platform admin."""
    effective = list(roles or [])
    if (
        email
        and email.strip().lower() in platform_admin_emails(configured)
        and Roles.ADMIN not in effective
    ):
        effective.append(Roles.ADMIN.value)
    return effective
