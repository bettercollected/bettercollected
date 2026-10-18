"""Admin service settings, read from the environment.

Failures name the variable and never include its value: both settings carry
secrets (a database password, the master key).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping

from common.settings.crypto.keys import (
    MASTER_KEY_KEY,
    MIN_MASTER_KEY_BYTES,
    MasterKeyError,
)
from common.settings.crypto.keys import parse_master_key as _parse_master_key

DATABASE_URL_KEY = "ADMIN_DATABASE_URL"
ASYNC_SCHEME = "postgresql+asyncpg://"


class AdminConfigError(RuntimeError):
    """The environment cannot run the admin service; the message is safe to log."""


def parse_master_key(raw: str | None) -> bytes:
    """Decode a base64 master key of at least 32 bytes, or raise without echoing it."""
    try:
        return _parse_master_key(raw)
    except MasterKeyError as exc:
        raise AdminConfigError(str(exc)) from None


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
