"""Loader configuration, read from the environment.

``SETTINGS_STORE`` is ``off``, ``auto`` or ``required``:

* ``off``: the store is never read; settings come from the environment and
  defaults exactly as before.
* ``auto`` (the default): the store is used when both ``DATABASE_URL`` and
  ``SETTINGS_MASTER_KEY`` are set, otherwise it behaves like ``off``. A store
  that cannot be read is logged and skipped.
* ``required``: the service must be able to read the store (or a still valid
  signed disk snapshot, or find every critical key in the environment); a
  problem with a critical key at start-up stops the service.
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from typing import Mapping, Optional

from ..registry import normalize_value

__all__ = ["LoaderConfig", "MODES"]

MODES = ("off", "auto", "required")
SERVICE_NAME = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


def _text(env: Mapping[str, Optional[str]], key: str) -> str:
    return normalize_value(env.get(key))


def _number(env: Mapping[str, Optional[str]], key: str, default: float, low: float) -> float:
    raw = _text(env, key)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"{key} must be a number") from None
    if value < low:
        raise ValueError(f"{key} must be at least {low:g}")
    return value


@dataclass(frozen=True)
class LoaderConfig:
    service: str
    mode: str
    database_url: str = ""
    master_key: str = ""
    master_key_previous: str = ""
    snapshot_dir: str = ""
    snapshot_max_age_days: float = 7.0
    connect_timeout: float = 3.0
    statement_timeout: float = 3.0
    retries: int = 3
    total_budget: float = 10.0
    poll_interval: float = 10.0
    poll_jitter: float = 3.0

    def __repr__(self) -> str:  # never show the URL (credentials) or a key
        return f"LoaderConfig(service={self.service!r}, mode={self.mode!r})"

    @property
    def configured(self) -> bool:
        return bool(self.database_url and self.master_key)

    @property
    def active(self) -> bool:
        """Whether the store is read at all."""
        return self.mode == "required" or (self.mode == "auto" and self.configured)

    @classmethod
    def from_env(
        cls, service: str, env: Optional[Mapping[str, Optional[str]]] = None
    ) -> "LoaderConfig":
        env = os.environ if env is None else env
        if not SERVICE_NAME.match(service or ""):
            raise ValueError("service name must be lowercase letters, digits or underscore")
        mode = (_text(env, "SETTINGS_STORE") or "auto").lower()
        if mode not in MODES:
            raise ValueError("SETTINGS_STORE must be off, auto or required")
        uid = os.geteuid() if hasattr(os, "geteuid") else 0
        directory = _text(env, "SETTINGS_SNAPSHOT_DIR") or os.path.join(
            tempfile.gettempdir(), f"bc-settings-{uid}"
        )
        return cls(
            service=service,
            mode=mode,
            database_url=_text(env, "DATABASE_URL"),
            master_key=_text(env, "SETTINGS_MASTER_KEY"),
            master_key_previous=_text(env, "SETTINGS_MASTER_KEY_PREVIOUS"),
            snapshot_dir=directory,
            snapshot_max_age_days=_number(env, "SETTINGS_SNAPSHOT_MAX_AGE_DAYS", 7.0, 1.0),
        )
