"""``live()``: read hot (class H) settings without a restart.

    live().ai.RATE_LIMIT_PER_USER

A group is a settings instance that was exposed once, at start-up:
``expose_live("ai", settings.ai)``. Reading ``live().ai.X`` returns the
store's verified value when ``AI_X`` (the instance's env prefix plus the field
name) is a hot, non-secret registry key, the environment does not override it
and a verified row exists; otherwise the instance's own value, which is fixed
until restart. A key that is not class H can therefore never change under a
running process, and ``live()`` works the same with the store off.

``live().get("KEY", default)`` reads a registry key directly.
"""

from __future__ import annotations

from typing import Any, Dict

from .poller import ensure_poller
from .runtime import current_runtime

__all__ = ["expose_live", "live"]

_groups: Dict[str, "LiveGroup"] = {}


def _prefix(instance: Any) -> str:
    return str(getattr(type(instance), "model_config", {}).get("env_prefix", "") or "")


class LiveGroup:
    def __init__(self, instance: Any):
        object.__setattr__(self, "_instance", instance)
        object.__setattr__(self, "_prefix", _prefix(instance).upper())

    def __getattr__(self, name: str) -> Any:
        instance = object.__getattribute__(self, "_instance")
        if name.startswith("_") or name not in type(instance).model_fields:
            raise AttributeError(name)
        runtime = current_runtime()
        if runtime is not None:
            found, value = runtime.live_value(self._prefix + name.upper())
            if found:
                return value
        return getattr(instance, name)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("live settings are read only")


class _Live:
    def __getattr__(self, name: str) -> LiveGroup:
        ensure_poller()  # lazily, so a forked worker has its own poller
        try:
            return _groups[name]
        except KeyError:
            raise AttributeError(f"no live settings group {name!r}") from None

    def get(self, key: str, default: Any = None) -> Any:
        ensure_poller()
        runtime = current_runtime()
        if runtime is not None:
            found, value = runtime.live_value(key)
            if found:
                return value
        return default


_live = _Live()


def live() -> _Live:
    return _live


def expose_live(name: str, instance: Any) -> Any:
    """Make ``live().<name>`` read hot keys of ``instance``. Returns it."""
    _groups[name] = LiveGroup(instance)
    return instance
