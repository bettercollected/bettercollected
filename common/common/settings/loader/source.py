"""Where a loader gets its rows: a small protocol and a Postgres implementation.

The Postgres source reads only the security-barrier views of its service
(``settings.v_<service>`` and ``settings.v_<service>_manifest``) and calls
``settings.report_state``. It uses asyncpg (already a dependency of every
service) on a private event loop in a helper thread, so it works at import
time and also when called from code that is already inside a running loop.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import socket
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional, Protocol, Tuple, runtime_checkable

from ..canonical import SettingRow
from ..signing import Manifest
from ..snapshot import ServiceState

__all__ = [
    "PgSnapshotSource",
    "RawSnapshot",
    "SnapshotSource",
    "SourceUnavailable",
    "instance_id",
    "instance_role",
    "set_instance_role",
]

_SERVICE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


class SourceUnavailable(Exception):
    """The store could not be read (connection, timeout, permission, schema).
    The message never contains a value or connection details."""


@dataclass
class RawSnapshot:
    """What the store returned, before any verification."""

    rows: List[SettingRow] = field(default_factory=list)
    manifest: Optional[Manifest] = None
    malformed: List[Tuple[str, int]] = field(default_factory=list)  # (key, version)


@runtime_checkable
class SnapshotSource(Protocol):
    def fetch(self) -> RawSnapshot:
        """Rows visible to the service and the whole signed manifest, read in
        one consistent transaction. Raises ``SourceUnavailable``."""
        ...

    def fetch_revision(self) -> Optional[int]:
        """The manifest revision only (cheap). Raises ``SourceUnavailable``."""
        ...

    def report_state(self, instance: str, state: ServiceState) -> None:
        """Raises ``SourceUnavailable``."""
        ...


def _clean(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.:-]", "-", raw)


_ROLE = re.compile(r"^[a-z][a-z0-9]{0,15}$")
_instance_role: Optional[str] = None


def set_instance_role(role: Optional[str]) -> None:
    """Name the component this process is in its heartbeat (``jobs`` for the
    backend's job worker; ``None`` for the service's main process). Call it
    before the settings load, which starts the heartbeat. It only labels the
    instance: the service a heartbeat belongs to is the database role that
    reports it. Not an environment setting on purpose: nothing an operator
    sets can rename an instance."""
    global _instance_role
    if role is not None and not _ROLE.match(role):
        raise ValueError("an instance role is a short lower-case word")
    _instance_role = role


def instance_role() -> Optional[str]:
    return _instance_role


def instance_id(
    service: str = "service", directory: Optional[str] = None, role: Optional[str] = None
) -> str:
    """A stable id per container: ``service:hostname`` (the container hostname
    lives as long as the container, so recreating containers cannot pile up
    reported states), ``service.role:hostname`` for a component that runs
    beside the service's main process (``role``). Without a usable hostname, a
    random id kept in ``directory`` (mode 600); without that, a random id for
    this process. Letters, digits and ``_.:-`` only, at most 64 characters."""
    name = f"{service}.{role}" if role and _ROLE.match(role) else service
    host = _clean(socket.gethostname() or "").strip("-")
    if host and host.lower() not in ("localhost", "localhost.localdomain"):
        return f"{name}:{host}"[:64]
    if directory:
        path = os.path.join(directory, f"instance-{name}")
        try:
            with open(path, "r", encoding="ascii") as handle:
                saved = _clean(handle.read().strip())
            if saved:
                return f"{name}:{saved}"[:64]
        except OSError:
            pass
        token = secrets.token_hex(8)
        try:
            os.makedirs(directory, mode=0o700, exist_ok=True)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="ascii") as handle:
                handle.write(token)
        except OSError:
            pass
        return f"{name}:{token}"[:64]
    return f"{name}:{secrets.token_hex(8)}"[:64]


def libpq_url(url: str) -> str:
    """``postgresql+asyncpg://...`` to ``postgresql://...``."""
    scheme, sep, rest = url.partition("://")
    if not sep:
        raise ValueError("DATABASE_URL is not a URL")
    return f"{scheme.split('+')[0]}://{rest}"


def _run(coro_factory, timeout: float):
    """Run a coroutine to completion on its own loop in a helper thread."""
    box: dict = {}

    def target() -> None:
        try:
            box["result"] = asyncio.run(coro_factory())
        except BaseException as exc:  # noqa: BLE001 - re-raised as a class name only
            box["error"] = exc

    thread = threading.Thread(target=target, name="settings-store-io", daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise SourceUnavailable("timeout")
    if "error" in box:
        raise SourceUnavailable(type(box["error"]).__name__)
    return box.get("result")


def _loads(raw: Any) -> Any:
    return json.loads(raw) if isinstance(raw, (str, bytes)) else raw


def build_row(record: Any) -> SettingRow:
    updated_at = record["updated_at"]
    if not isinstance(updated_at, datetime):
        raise ValueError("updated_at")
    value = record["value"]
    return SettingRow(
        key=record["key"],
        section=record["section"],
        readers=tuple(record["readers"]),
        is_secret=bool(record["is_secret"]),
        reload_class=record["reload_class"],
        version=int(record["version"]),
        updated_at=updated_at,
        value=None if value is None else _loads(value),
        blob=record["blob"],
        sig=record["sig"] or "",
    )


def build_manifest(record: Any) -> Manifest:
    return Manifest(
        int(record["revision"]),
        dict(_loads(record["entries"]) or {}),
        record["sig"] or "",
    )


class PgSnapshotSource:
    def __init__(
        self,
        database_url: str,
        service: str,
        *,
        connect_timeout: float = 3.0,
        statement_timeout: float = 3.0,
    ):
        if not _SERVICE.match(service):  # the name becomes part of a view name
            raise ValueError("invalid service name")
        self._dsn = libpq_url(database_url)
        self._service = service
        self._connect_timeout = connect_timeout
        self._statement_timeout = statement_timeout

    def __repr__(self) -> str:
        return f"PgSnapshotSource(service={self._service!r})"

    @property
    def _hard_timeout(self) -> float:
        return self._connect_timeout + self._statement_timeout + 2.0

    async def _connect(self):
        import asyncpg  # lazy: only a service that reads the store needs it

        return await asyncpg.connect(
            self._dsn,
            timeout=self._connect_timeout,
            command_timeout=self._statement_timeout,
            server_settings={
                "statement_timeout": str(int(self._statement_timeout * 1000)),
                "application_name": f"bc-settings-{self._service}",
            },
        )

    def fetch(self) -> RawSnapshot:
        service = self._service

        async def go() -> RawSnapshot:
            conn = await self._connect()
            try:
                async with conn.transaction(isolation="repeatable_read", readonly=True):
                    manifest = await conn.fetchrow(
                        f"SELECT revision, entries, sig FROM settings.v_{service}_manifest"
                    )
                    records = await conn.fetch(
                        "SELECT key, section, readers, is_secret, reload_class, value, "
                        f"blob, version, updated_at, sig FROM settings.v_{service}"
                    )
            finally:
                await conn.close()
            raw = RawSnapshot()
            raw.manifest = build_manifest(manifest) if manifest is not None else None
            for record in records:
                try:
                    raw.rows.append(build_row(record))
                except Exception:  # noqa: BLE001 - reported by key and version
                    raw.malformed.append((str(record["key"])[:64], int(record["version"] or 0)))
            return raw

        return _run(go, self._hard_timeout)

    def fetch_revision(self) -> Optional[int]:
        service = self._service

        async def go() -> Optional[int]:
            conn = await self._connect()
            try:
                row = await conn.fetchrow(f"SELECT revision FROM settings.v_{service}_manifest")
            finally:
                await conn.close()
            return None if row is None else int(row["revision"])

        return _run(go, self._hard_timeout)

    def report_state(self, instance: str, state: ServiceState) -> None:
        report = state.to_report()

        async def go() -> None:
            conn = await self._connect()
            try:
                args = (
                    instance,
                    int(report["revision_applied"]),
                    list(report["env_overrides"]),
                    list(report["rejected_keys"]),
                    bool(report["restart_pending"]),
                    str(report["keyset_fp"]),
                )
                try:
                    await conn.execute(
                        "SELECT settings.report_state($1, $2, $3, $4, $5, $6, $7)",
                        *args,
                        str(report.get("write_stores", "")),
                    )
                except Exception as exc:  # noqa: BLE001
                    # a store from before admin revision 0018 (rolling deploy):
                    # report without the write stores
                    if getattr(exc, "sqlstate", None) != "42883":  # undefined_function
                        raise
                    await conn.execute(
                        "SELECT settings.report_state($1, $2, $3, $4, $5, $6)", *args
                    )
            finally:
                await conn.close()

        _run(go, self._hard_timeout)
