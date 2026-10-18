"""The loader: one verified snapshot of the store per process.

``load_snapshot(service)`` reads the store once (synchronously, at import time
of the settings classes), verifies it with ``verify_snapshot(service=...)`` and
keeps the result. Resolution order for a setting is the environment (set and
non-empty), then the verified store row, then the default.

Failure policy
--------------
* Reachable store, bad row: the row is refused and the last good value (from
  this process) is kept; a key never accepted falls back to its default (a
  secret has no default). The disk snapshot is NOT consulted.
* Critical keys (secrets, tier T3 and T4) that were rejected, with no last
  good value and nothing in the environment, stop a ``required`` service at
  start-up. After start-up nothing stops the service; it keeps what it has.
* Unreachable store: the signed disk snapshot, re-verified and not older than
  ``SETTINGS_SNAPSHOT_MAX_AGE_DAYS``. With no usable snapshot a ``required``
  service starts only if the environment holds every key in
  ``required_env_keys``.
* The highest manifest revision and row versions seen (also seeded from the
  disk snapshot, if it verifies) are never accepted downwards. After restoring
  the database from a backup, remove the snapshot directory.

Messages name keys and versions, never values.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Set, Tuple

from ..canonical import SettingRow
from ..keys import SectionKeys
from ..registry import Registry, Reload, Tier, ValidationError, default_registry, normalize_value
from ..resolve import ResolveError, Resolved, Source, resolve
from ..signing import MonotonicTracker
from ..snapshot import (
    Rejection,
    ServiceState,
    Verification,
    VerifiedSettings,
    verify_snapshot,
)
from .config import LoaderConfig
from .disk import SnapshotError, read_snapshot, write_snapshot
from .source import (
    PgSnapshotSource,
    RawSnapshot,
    SnapshotSource,
    SourceUnavailable,
    instance_id,
)

__all__ = [
    "SettingsRuntime",
    "StoreError",
    "current_runtime",
    "keyset_fingerprint",
    "load_snapshot",
    "reset",
    "set_keyset_key_ids",
]

log = logging.getLogger("common.settings.loader")
_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
UNTRUSTED = "*"


class StoreError(RuntimeError):
    """The service must not start. The message names keys, never values."""


# ------------------------------------------------------------ keyset hook

_key_ids_provider: Optional[Callable[[], Iterable[Any]]] = None


def keyset_fingerprint(key_ids: Iterable[Any]) -> str:
    """Short hash of the key ids of a keyset (ids only, never key material)."""
    ids = sorted(str(i) for i in key_ids)
    digest = hashlib.sha256(("bc-keyset-v1|" + ",".join(ids)).encode()).hexdigest()
    return "ks-" + digest[:12]


def set_keyset_key_ids(provider: Optional[Callable[[], Iterable[Any]]]) -> None:
    """Register how to list the key ids of the loaded ``MASTER_ENCRYPTION_KEYSET``
    (called by the service that parses it; this package never imports it)."""
    global _key_ids_provider
    _key_ids_provider = provider


# ------------------------------------------------------------ the runtime


class SettingsRuntime:
    def __init__(
        self,
        config: LoaderConfig,
        *,
        registry: Optional[Registry] = None,
        source: Optional[SnapshotSource] = None,
        required_env_keys: Iterable[str] = (),
        env: Optional[Mapping[str, Optional[str]]] = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.config = config
        self.service = config.service
        self.registry = registry or default_registry()
        self.env = os.environ if env is None else env
        self.required_env_keys = tuple(required_env_keys)
        self._clock, self._sleep, self._now = clock, sleep, now
        self.tracker = MonotonicTracker()
        self.current = VerifiedSettings(Verification({}, [], 0))
        self.origin = "none"  # none | store | snapshot
        self.restart_pending = False
        self._seen_revision = -1
        self.last_rejections: Tuple[Rejection, ...] = ()
        self._logged: Set[Tuple[str, int, str]] = set()
        self.lock = threading.RLock()
        sections = {s.section for s in self.registry.for_reader(self.service)}
        self.keys: Optional[SectionKeys] = None
        if config.master_key:
            try:
                self.keys = SectionKeys(
                    config.master_key,
                    sections=sections,
                    master_previous=config.master_key_previous or None,
                )
            except Exception:  # noqa: BLE001 - never echo the key or the cause
                raise StoreError("SETTINGS_MASTER_KEY (or the previous key) is not valid") from None
        if source is None and config.database_url:
            source = PgSnapshotSource(
                config.database_url,
                self.service,
                connect_timeout=config.connect_timeout,
                statement_timeout=config.statement_timeout,
            )
        self.source = source

    # ---- helpers

    def _env_has(self, key: str) -> bool:
        return bool(normalize_value(self.env.get(key)))

    def critical_keys(self) -> Set[str]:
        return {
            s.key
            for s in self.registry.for_reader(self.service)
            if s.is_secret or s.tier in (Tier.T3, Tier.T4)
        }

    def env_overrides(self) -> Tuple[str, ...]:
        return tuple(
            sorted(s.key for s in self.registry.for_reader(self.service) if self._env_has(s.key))
        )

    @property
    def revision(self) -> int:
        return self.current.revision

    def _log_rejections(self, rejections: Iterable[Rejection]) -> None:
        for r in rejections:
            token = (r.key, r.version, r.reason)
            if token not in self._logged and len(self._logged) < 5000:
                self._logged.add(token)
                log.warning("%s", r.message())

    # ---- verification and application

    def _verify(self, raw: RawSnapshot) -> Tuple[Verification, bool]:
        """The verification and whether the manifest was trusted. A store that
        was never written (revision 0, no rows) is trusted and empty."""
        m = raw.manifest
        if (
            m is not None
            and m.revision == 0
            and not m.sig
            and not raw.rows
            and not raw.malformed
            and self.tracker.revision == 0
        ):
            return Verification({}, [], 0), True
        if self.keys is None:
            raise StoreError("SETTINGS_MASTER_KEY is required to verify the settings store")
        v = verify_snapshot(
            raw.rows,
            m,
            self.keys,
            self.tracker,
            registry=self.registry,
            service=self.service,
        )
        trusted = not any(r.key == UNTRUSTED for r in v.rejections)
        if raw.malformed:
            extra = [Rejection(k, ver, "malformed_row") for k, ver in raw.malformed]
            v = Verification(v.accepted, list(v.rejections) + extra, v.revision)
        return v, trusted

    def _check_critical(self, rejections: List[Rejection], trusted: bool) -> None:
        bad = {r.key for r in rejections}
        failing = self.critical_keys() if not trusted else self.critical_keys() & bad
        failing = {k for k in failing if self.current.get(k) is None and not self._env_has(k)}
        if failing:
            why = "the signed manifest was not trusted" if not trusted else "rows were refused"
            raise StoreError(
                f"settings store: {why}; no usable value for critical settings: "
                + ", ".join(sorted(failing))
            )

    def _apply(
        self, raw: RawSnapshot, *, startup: bool, origin: str, check: bool = True
    ) -> bool:
        v, trusted = self._verify(raw)
        self._log_rejections(v.rejections)
        if not trusted:
            self.last_rejections = tuple(v.rejections)
            self._seen_revision = (
                raw.manifest.revision if raw.manifest is not None else self._seen_revision
            )
            if startup and check and self.config.mode == "required":
                self._check_critical(list(v.rejections), False)
            return False
        if startup and check and self.config.mode == "required":
            self._check_critical(list(v.rejections), True)
        new = VerifiedSettings(v, previous=self.current)
        with self.lock:
            old = self.current
            self.tracker.commit(v.accepted.values(), v.revision)
            if not startup:
                self._note_restart(old, new)
            self.current = new
            self.origin = origin
            self._seen_revision = v.revision
        return True

    def _note_restart(self, old: VerifiedSettings, new: VerifiedSettings) -> None:
        for key in set(old._rows) | set(new._rows):
            before, after = old.get(key), new.get(key)
            if (before.version if before else None) == (after.version if after else None):
                continue
            if key in self.registry and not self._env_has(key):
                if self.registry.get(key).reload_class is Reload.R:
                    self.restart_pending = True

    def _write_disk(self, raw: RawSnapshot) -> None:
        v = self.current
        if raw.manifest is None or raw.manifest.revision == 0:
            return
        rows = [r for k in sorted(v._rows) if (r := v._rows[k]) and k not in v.stale_keys]
        try:
            write_snapshot(self.config.snapshot_dir, self.service, rows, raw.manifest, self._now())
        except (SnapshotError, OSError) as exc:
            log.warning("settings snapshot not written (%s)", type(exc).__name__)

    def _seed_from_disk(self) -> None:
        """Remember the revision and versions of a valid snapshot so a replayed
        older store is refused after a restart."""
        if self.keys is None:
            return
        try:
            raw, _ = read_snapshot(
                self.config.snapshot_dir, self.service, None, self._now()
            )
            v = verify_snapshot(
                raw.rows, raw.manifest, self.keys, MonotonicTracker(),
                registry=self.registry, service=self.service,
            )
        except Exception:  # noqa: BLE001 - an unusable snapshot seeds nothing
            return
        if not any(r.key == UNTRUSTED for r in v.rejections):
            self.tracker.commit(v.accepted.values(), v.revision)

    # ---- start-up

    def _fetch(self) -> RawSnapshot:
        assert self.source is not None
        cfg = self.config
        start, last = self._clock(), None
        for attempt in range(max(1, cfg.retries)):
            try:
                return self.source.fetch()
            except SourceUnavailable as exc:
                last = exc
                log.warning("settings store unavailable (%s), attempt %d", exc, attempt + 1)
            delay = 0.25 * (2**attempt)
            if attempt + 1 >= cfg.retries or self._clock() - start + delay >= cfg.total_budget:
                break
            self._sleep(delay)
        raise last or SourceUnavailable("unavailable")

    def start(self) -> None:
        try:
            self._start()
        finally:
            self._warn_unset_critical()

    def _warn_unset_critical(self) -> None:
        """Once, names only: secret and T3 settings with neither an environment
        value nor a verified store row, so a misconfigured deployment is
        visible without blocking the start."""
        unset = sorted(
            s.key
            for s in self.registry.for_reader(self.service)
            if (s.is_secret or s.tier is Tier.T3)
            and not self._env_has(s.key)
            and self.current.get(s.key) is None
        )
        if unset:
            log.warning(
                "settings with no value from the environment or the store (%d): %s",
                len(unset),
                ", ".join(unset),
            )

    def _start(self) -> None:
        cfg = self.config
        if cfg.mode == "required" and not cfg.configured:
            raise StoreError("SETTINGS_STORE=required needs DATABASE_URL and SETTINGS_MASTER_KEY")
        self._seed_from_disk()
        if self.source is None:
            return self._start_without_store("no database")
        try:
            raw = self._fetch()
        except SourceUnavailable:
            return self._start_from_snapshot()
        if self._apply(raw, startup=True, origin="store"):
            self._write_disk(raw)
        log.info(
            "settings loaded from the store: revision %d, %d overridden by the environment",
            self.revision,
            len(self.env_overrides()),
        )

    def _start_from_snapshot(self) -> None:
        try:
            raw, saved = read_snapshot(
                self.config.snapshot_dir, self.service, self.config.snapshot_max_age_days, self._now()
            )
        except SnapshotError as exc:
            return self._start_without_store(f"snapshot {exc.reason}")
        if not self._apply(raw, startup=True, origin="snapshot", check=False):
            return self._start_without_store("snapshot not trusted")
        log.warning(
            "settings store unreachable: using the signed snapshot (revision %d, saved %s)",
            self.revision,
            saved.date().isoformat(),
        )
        if self.config.mode == "required":
            self._check_critical(list(self.current.rejections), True)

    def _start_without_store(self, why: str) -> None:
        missing = [k for k in self.required_env_keys if not self._env_has(k)]
        if self.config.mode == "required" and missing:
            raise StoreError(
                f"settings store unavailable ({why}) and the environment does not supply: "
                + ", ".join(sorted(missing))
            )
        log.warning("settings store not used (%s): environment and defaults only", why)

    # ---- resolution

    def resolve_key(self, key: str, default: Any = None) -> Optional[Resolved]:
        """The store's value for ``key`` when the store is the source, else None
        (the environment, or a key the store does not serve)."""
        if key not in self.registry or self.service not in self.registry.get(key).readers:
            return None
        if self._env_has(key):
            return None
        row = self.current.get(key)
        if row is None or self.keys is None:
            return None
        keys = self.keys
        try:
            resolved = resolve(
                key, {}, row, default, self.registry,
                open_secret=lambda r: keys.open(r.section, r.key, r.version, r.blob or ""),
            )
        except ResolveError as exc:
            log.warning("%s", exc)
            if self.config.mode == "required" and key in self.critical_keys():
                raise StoreError(f"settings store: no usable value for critical setting {key}") from None
            return None
        return resolved if resolved.source is Source.STORE else None

    def live_value(self, key: str) -> Tuple[bool, Any]:
        """``(True, value)`` for a hot (class H), non-secret key whose store row
        is verified and not overridden by the environment."""
        if key not in self.registry:
            return False, None
        spec = self.registry.get(key)
        if spec.reload_class is not Reload.H or spec.is_secret or self.service not in spec.readers:
            return False, None
        if self._env_has(key):
            return False, None
        row = self.current.get(key)
        if row is None:
            return False, None
        try:
            return True, self.registry.coerce(key, row.value)
        except ValidationError:
            return False, None

    # ---- reload and reporting

    def keyset_fp(self) -> str:
        provider = _key_ids_provider
        if provider is not None:
            try:
                return keyset_fingerprint(provider())
            except Exception as exc:  # noqa: BLE001
                log.warning("keyset fingerprint unavailable (%s)", type(exc).__name__)
        return self.keys.fingerprint if self.keys else ""

    def state(self) -> ServiceState:
        rejected = {
            r.key for r in self.current.rejections if _NAME.match(r.key)
        } | {r.key for r in self.last_rejections if _NAME.match(r.key)}
        return ServiceState(
            service=self.service,
            revision_applied=max(self.revision, 0),
            env_overrides=self.env_overrides(),
            rejected_keys=tuple(sorted(rejected)),
            restart_pending=self.restart_pending,
            keyset_fp=self.keyset_fp(),
        )

    def report(self) -> None:
        """Tell the store what this process applied. Raises ``SourceUnavailable``."""
        if self.source is not None:
            self.source.report_state(
                instance_id(self.service, self.config.snapshot_dir), self.state()
            )

    def poll_once(self) -> bool:
        """Check the manifest revision and apply a newer snapshot. True when the
        snapshot changed. Raises ``SourceUnavailable`` when the store is down."""
        if self.source is None:
            return False
        revision = self.source.fetch_revision()
        if revision is None or revision == self._seen_revision:
            return False
        raw = self.source.fetch()
        self.last_rejections = ()
        applied = self._apply(raw, startup=False, origin="store")
        if applied:
            self._write_disk(raw)
        self.report_safely()
        return applied

    def report_safely(self) -> None:
        try:
            self.report()
        except Exception as exc:  # noqa: BLE001 - never crash on a heartbeat
            log.warning("settings state not reported (%s)", type(exc).__name__)


# ------------------------------------------------------------ process-wide

_lock = threading.Lock()
_runtime: Optional[SettingsRuntime] = None
_service: Optional[str] = None


def current_runtime() -> Optional[SettingsRuntime]:
    return _runtime


def load_snapshot(
    service: str,
    *,
    required_env_keys: Iterable[str] = (),
    env: Optional[Mapping[str, Optional[str]]] = None,
    source: Optional[SnapshotSource] = None,
    registry: Optional[Registry] = None,
) -> Optional[SettingsRuntime]:
    """Load the process's one snapshot for ``service`` (idempotent). Returns the
    runtime, or None when the store is off (``SETTINGS_STORE=off``, or ``auto``
    without ``DATABASE_URL`` and ``SETTINGS_MASTER_KEY``). Raises ``StoreError``
    when a ``required`` service must not start."""
    global _runtime, _service
    with _lock:
        if _service is not None:
            if _service != service:
                raise StoreError("the settings snapshot of this process belongs to another service")
            return _runtime
        config = LoaderConfig.from_env(service, env)
        if source is None and not config.active:
            _service = service
            return None
        runtime = SettingsRuntime(
            config, registry=registry, source=source, required_env_keys=required_env_keys, env=env
        )
        runtime.start()
        _runtime, _service = runtime, service
        return runtime


def reset() -> None:
    """Forget the process's snapshot (tests)."""
    global _runtime, _service
    from .poller import stop_poller

    stop_poller()
    with _lock:
        _runtime = _service = None
