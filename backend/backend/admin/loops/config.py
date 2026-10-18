"""Loop settings from the environment (``ADMIN_`` names, env only)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Optional

from backend.admin.portal_config import PortalConfigError


def _flag(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = (env.get(name) or "").strip().lower()
    if not raw:
        return default
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    raise PortalConfigError(f"{name} must be true or false")


def _whole(env: Mapping[str, str], name: str, default: int, low: int, high: int) -> int:
    raw = (env.get(name) or "").strip()
    if not raw:
        return default
    if not raw.isascii() or not raw.isdigit() or not low <= int(raw) <= high:
        raise PortalConfigError(f"{name} must be a whole number from {low} to {high}")
    return int(raw)


@dataclass(frozen=True)
class LoopSettings:
    enabled: bool = True
    notify_interval: int = 15  # seconds between outbox passes
    notify_max_per_minute: int = 30  # mails, not rows
    retention_interval: int = 3600
    integrity_interval: int = 600

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "LoopSettings":
        source = os.environ if env is None else env
        return cls(
            enabled=_flag(source, "ADMIN_LOOPS_ENABLED", True),
            notify_interval=_whole(source, "ADMIN_NOTIFY_INTERVAL_SECONDS", 15, 1, 3600),
            notify_max_per_minute=_whole(source, "ADMIN_NOTIFY_MAX_PER_MINUTE", 30, 1, 600),
            retention_interval=_whole(
                source, "ADMIN_RETENTION_INTERVAL_SECONDS", 3600, 10, 86400
            ),
            integrity_interval=_whole(
                source, "ADMIN_INTEGRITY_INTERVAL_SECONDS", 600, 10, 86400
            ),
        )
