"""Admin service settings, read from the environment.

Failures name the variable and never include its value: both settings carry
secrets (a database password, the master key).
"""

from __future__ import annotations

import base64
import binascii
import os
from dataclasses import dataclass, field
from typing import Mapping

DATABASE_URL_KEY = "ADMIN_DATABASE_URL"
MASTER_KEY_KEY = "SETTINGS_MASTER_KEY"
MIN_MASTER_KEY_BYTES = 32
ASYNC_SCHEME = "postgresql+asyncpg://"


class AdminConfigError(RuntimeError):
    """The environment cannot run the admin service; the message is safe to log."""


def parse_master_key(raw: str | None) -> bytes:
    """Decode a base64 master key of at least 32 bytes, or raise without echoing it."""
    value = (raw or "").strip()
    if not value:
        raise AdminConfigError(
            f"{MASTER_KEY_KEY} is not set. Generate one with "
            f"`openssl rand -base64 48` and keep it: without it the stored second-factor "
            f"secrets and the audit chain cannot be recovered or verified."
        )
    padded = value + "=" * (-len(value) % 4)
    key = None
    for altchars in (None, b"-_"):  # standard, then URL-safe alphabet
        try:
            key = base64.b64decode(padded, altchars=altchars, validate=True)
            break
        except (binascii.Error, ValueError):
            continue
    if key is None:
        raise AdminConfigError(
            f"{MASTER_KEY_KEY} is not valid base64 (value not shown)."
        )
    if len(key) < MIN_MASTER_KEY_BYTES:
        raise AdminConfigError(
            f"{MASTER_KEY_KEY} must decode to at least {MIN_MASTER_KEY_BYTES} bytes "
            f"(value not shown)."
        )
    return key


def parse_database_url(raw: str | None) -> str:
    value = (raw or "").strip()
    if not value:
        raise AdminConfigError(f"{DATABASE_URL_KEY} is not set.")
    for prefix in ("postgresql://", "postgres://"):
        if value.startswith(prefix):
            return ASYNC_SCHEME + value[len(prefix) :]
    if not value.startswith(ASYNC_SCHEME):
        raise AdminConfigError(
            f"{DATABASE_URL_KEY} must be a postgresql:// or {ASYNC_SCHEME} URL "
            f"(value not shown)."
        )
    return value


@dataclass(frozen=True)
class AdminSettings:
    database_url: str = field(repr=False)
    master_key: bytes = field(repr=False)

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "AdminSettings":
        return cls(
            database_url=parse_database_url(env.get(DATABASE_URL_KEY)),
            master_key=parse_master_key(env.get(MASTER_KEY_KEY)),
        )
