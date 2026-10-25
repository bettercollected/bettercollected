"""What single sign-on needs on each service, by setting name (docs/sso.md).

``SSO_ENABLED=true`` alone does not make single sign-on work: each service also
needs the identity bridge's (Polis's) address and the callback address, and the
backend its admin API key. The services use this to say, at startup and on the
workspace page, that SSO is switched on but not fully set up; the admin portal
uses it to list the missing settings on its Health page.

Names only: nothing here reads, returns or logs a value.
"""

from __future__ import annotations

from typing import Callable, Mapping, Tuple

DISABLED = "disabled"
NOT_CONFIGURED = "not_configured"

ENABLED_KEY = "SSO_ENABLED"

# Settings a service cannot run single sign-on without. SSO_POLIS_INTERNAL_URL
# is not listed: it falls back to SSO_POLIS_URL.
REQUIRED: Mapping[str, Tuple[str, ...]] = {
    "backend": ("SSO_POLIS_URL", "SSO_POLIS_API_KEY", "SSO_REDIRECT_URI"),
    "auth": ("SSO_POLIS_URL", "SSO_REDIRECT_URI"),
}

# Settings a service uses when set but works without. Auth sends the client
# secret on the code exchange when set; every sign-in also uses PKCE.
OPTIONAL: Mapping[str, Tuple[str, ...]] = {
    "auth": ("SSO_POLIS_CLIENT_SECRET",),
}


def missing(service: str, is_set: Callable[[str], bool]) -> Tuple[str, ...]:
    """The names of ``service``'s required settings that ``is_set`` says are
    not set, in a fixed order."""
    return tuple(name for name in REQUIRED.get(service, ()) if not is_set(name))


def missing_optional(service: str, is_set: Callable[[str], bool]) -> Tuple[str, ...]:
    return tuple(name for name in OPTIONAL.get(service, ()) if not is_set(name))


def status(enabled: bool, missing_names: Tuple[str, ...]) -> str | None:
    """``None`` when single sign-on can be used, ``"disabled"`` when it is
    switched off, ``"not_configured"`` when it is on but settings are missing."""
    if not enabled:
        return DISABLED
    return NOT_CONFIGURED if missing_names else None


def startup_message(service: str, missing_names: Tuple[str, ...]) -> str:
    """The startup log line: setting names only."""
    return (
        f"SSO_ENABLED is true but single sign-on is not fully set up on the {service} "
        f"service: missing {', '.join(missing_names)}. Single sign-on stays "
        "unavailable until these are set (see docs/sso.md)."
    )
