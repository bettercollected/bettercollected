"""Sign-in and session settings, read once from the environment.

Invalid values fail startup and never echo the value. Session lifetimes can be
made shorter than the defaults, never longer.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Optional, Tuple
from urllib.parse import urlsplit

from backend.admin.gate.settings import DEFAULT_PORT

ADMIN_EMAILS_KEY = "PLATFORM_ADMIN_EMAILS"
DEFAULT_IDLE_MINUTES = 30
DEFAULT_ABSOLUTE_HOURS = 8
MAX_SESSIONS = 3
CODE_TTL_SECONDS = 600


class PortalConfigError(ValueError):
    """The environment cannot run the sign-in; the message is safe to log."""


def parse_admin_emails(raw: Optional[str]) -> frozenset:
    """Lower-cased addresses from a comma- or semicolon-separated list."""
    out = set()
    for part in (raw or "").replace(";", ",").split(","):
        email = part.strip().lower()
        if email and "@" in email and not any(c.isspace() for c in email):
            out.add(email)
    return frozenset(out)


def normalise_origin(value: str, name: str = "ADMIN_PUBLIC_ORIGINS") -> str:
    """``scheme://host[:port]`` (lower case); anything else raises."""
    try:
        parts = urlsplit(value.strip())
        port = parts.port
    except ValueError:
        raise PortalConfigError(f"{name}: an entry is not an origin") from None
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.path not in ("", "/")
        or parts.query
        or parts.fragment
    ):
        raise PortalConfigError(f"{name}: entries must look like https://host[:port]")
    host = parts.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    return f"{parts.scheme}://{host}" + (f":{port}" if port is not None else "")


def _bounded(env: Mapping[str, str], name: str, default: int) -> int:
    raw = (env.get(name) or "").strip()
    if not raw:
        return default
    if not raw.isascii() or not raw.isdigit() or not 0 < int(raw) <= default:
        raise PortalConfigError(
            f"{name} must be a whole number from 1 to {default} (it can only be shortened)"
        )
    return int(raw)


@dataclass(frozen=True)
class PortalSettings:
    admin_emails: frozenset = frozenset()
    public_origins: Tuple[str, ...] = ()
    idle_minutes: int = DEFAULT_IDLE_MINUTES
    absolute_hours: int = DEFAULT_ABSOLUTE_HOURS
    max_sessions: int = MAX_SESSIONS
    code_ttl_seconds: int = CODE_TTL_SECONDS

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "PortalSettings":
        source = os.environ if env is None else env
        raw_port = (source.get("ADMIN_PORT") or str(DEFAULT_PORT)).strip()
        port = int(raw_port) if raw_port.isdigit() else DEFAULT_PORT
        raw_origins = [
            p.strip()
            for p in (source.get("ADMIN_PUBLIC_ORIGINS") or "").split(",")
            if p.strip()
        ] or [f"http://localhost:{port}", f"http://127.0.0.1:{port}"]
        return cls(
            admin_emails=parse_admin_emails(source.get(ADMIN_EMAILS_KEY)),
            public_origins=tuple(normalise_origin(o) for o in raw_origins),
            idle_minutes=_bounded(
                source, "ADMIN_SESSION_IDLE_MINUTES", DEFAULT_IDLE_MINUTES
            ),
            absolute_hours=_bounded(
                source, "ADMIN_SESSION_ABSOLUTE_HOURS", DEFAULT_ABSOLUTE_HOURS
            ),
        )

    def is_admin(self, email: str) -> bool:
        return str(email).strip().lower() in self.admin_emails
