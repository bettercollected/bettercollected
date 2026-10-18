"""A loader that lets services read settings from a signed, encrypted store,
with environment precedence (environment, then store, then default).

    runtime = load_snapshot("backend", required_env_keys=("AUTH_JWT_SECRET",))
    live().ai.RATE_LIMIT_PER_USER      # hot keys, after expose_live("ai", settings.ai)

See ``runtime`` for the failure policy. ``pydantic_source`` (not imported here)
holds the pydantic-settings glue. No ``crypto_service``, ``backend`` or FastAPI
import happens anywhere in this package.
"""

from .config import LoaderConfig
from .live import expose_live, live
from .poller import Poller, ensure_poller, stop_poller
from .runtime import (
    SettingsRuntime,
    StoreError,
    current_runtime,
    keyset_fingerprint,
    load_snapshot,
    reset,
    set_keyset_key_ids,
)
from .source import PgSnapshotSource, RawSnapshot, SnapshotSource, SourceUnavailable

__all__ = [
    "LoaderConfig",
    "PgSnapshotSource",
    "Poller",
    "RawSnapshot",
    "SettingsRuntime",
    "SnapshotSource",
    "SourceUnavailable",
    "StoreError",
    "current_runtime",
    "ensure_poller",
    "expose_live",
    "keyset_fingerprint",
    "live",
    "load_snapshot",
    "reset",
    "set_keyset_key_ids",
    "stop_poller",
]
