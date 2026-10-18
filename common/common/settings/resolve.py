"""The resolution rule for one setting: environment, then verified store row,
then default.

The environment counts only when set and non-empty after normalising (trim,
one pair of quotes), so an empty ``KEY=`` line in an env file never shadows
the store. Secrets are opened only when the store is the source, and a secret
with no source at all raises instead of defaulting.

A key whose store row was rejected keeps its last good value when the caller
reads it through ``VerifiedSettings(verification, previous=...)``; ``resolve``
just receives that row.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping, Optional

from .canonical import SettingRow
from .registry import Registry, ValidationError, normalize_value

__all__ = ["ResolveError", "Resolved", "Source", "resolve"]


class Source(str, Enum):
    ENV = "env"
    STORE = "store"
    DEFAULT = "default"


class ResolveError(ValueError):
    """A source supplied a value that cannot be used. Never contains it."""


@dataclass(frozen=True)
class Resolved:
    key: str
    value: Any
    source: Source
    overridden_by_env: bool  # the environment supplied the value

    def __repr__(self) -> str:  # a secret value never reaches a log line
        return f"Resolved(key={self.key!r}, source={self.source.value!r})"


def resolve(
    key: str,
    env: Mapping[str, Optional[str]],
    snapshot_row: Optional[SettingRow],
    default: Any,
    registry: Registry,
    *,
    open_secret: Optional[Callable[[SettingRow], str]] = None,
) -> Resolved:
    """``open_secret(row)`` returns a secret row's plaintext (for example
    ``lambda r: keys.open(r.section, r.key, r.version, r.blob)``); it is called
    only when the store row is chosen. Environment values get type checks only
    (policy such as URL rules applies to values written through the store)."""
    spec = registry.get(key)
    raw = normalize_value(env.get(key))
    if raw:
        try:
            return Resolved(key, registry.coerce(key, raw), Source.ENV, True)
        except ValidationError as exc:
            raise ResolveError(f"{key} in the environment is invalid ({exc.reason})") from None
    if snapshot_row is not None:
        if snapshot_row.key != key:
            raise ResolveError(f"{key}: row belongs to another setting")
        if spec.is_secret:
            if open_secret is None or snapshot_row.blob is None:
                raise ResolveError(f"{key}: cannot open the stored secret")
            try:
                value: Any = open_secret(snapshot_row)
            except Exception:  # noqa: BLE001 - fixed message: no cause, no content
                raise ResolveError(f"{key}: cannot open the stored secret") from None
        else:
            try:
                value = registry.coerce(key, snapshot_row.value)
            except ValidationError as exc:
                raise ResolveError(f"{key}: stored value is invalid ({exc.reason})") from None
        return Resolved(key, value, Source.STORE, False)
    if spec.is_secret:  # fail closed: a secret never falls back to a default
        raise ResolveError(f"{key}: a secret with no value from the environment or the store")
    return Resolved(key, default, Source.DEFAULT, False)
