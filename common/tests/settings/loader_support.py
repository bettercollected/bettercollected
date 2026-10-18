"""Helpers for the loader tests: a fake store source and signed rows."""

import copy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from settings_support import MASTER, MOMENT, plain_row

from common.settings.canonical import SettingRow
from common.settings.keys import SectionKeys
from common.settings.loader import LoaderConfig, SettingsRuntime, SourceUnavailable
from common.settings.loader.source import RawSnapshot
from common.settings.registry import default_registry
from common.settings.snapshot import FakeSnapshot, ServiceState

JWT = "AUTH_JWT_SECRET"
PLANTED = "PLANTED-SECRET-VALUE-0123456789"
ALL_SECTIONS = ["limits", "auth_keys", "rate_limits"]
BACKEND_ENV = {JWT: "", "AUTH_AES_HEX_KEY": ""}


def make_keys(master: str = MASTER) -> SectionKeys:
    return SectionKeys(master, sections=ALL_SECTIONS)


def jwt_row(keys: SectionKeys, plaintext: str = PLANTED, version: int = 1) -> SettingRow:
    blob = keys.seal("auth_keys", JWT, version, plaintext)
    return SettingRow(
        key=JWT,
        section="auth_keys",
        readers=("backend", "auth", "google"),
        is_secret=True,
        reload_class="R",
        version=version,
        updated_at=MOMENT,
        blob=blob,
    )


def rate_row(value: int = 5, version: int = 1) -> SettingRow:
    return SettingRow(
        key="API_FLOW_EVENTS_PER_WINDOW",
        section="rate_limits",
        readers=("backend",),
        is_secret=False,
        reload_class="H",
        version=version,
        updated_at=MOMENT,
        value=value,
    )


def raw_of(keys: SectionKeys, rows: List[SettingRow], revision: int = 1) -> RawSnapshot:
    snap = FakeSnapshot.build(rows, keys, revision)
    return RawSnapshot(list(snap.row_list), snap.signed_manifest)


class FakeSource:
    def __init__(self, raw: Optional[RawSnapshot] = None):
        self.raw = raw
        self.down = False
        self.report_down = False
        self.reports: List[ServiceState] = []
        self.fetches = 0

    def fetch(self) -> RawSnapshot:
        if self.down:
            raise SourceUnavailable("OSError")
        self.fetches += 1
        return copy.deepcopy(self.raw)

    def fetch_revision(self) -> Optional[int]:
        if self.down:
            raise SourceUnavailable("OSError")
        return self.raw.manifest.revision if self.raw and self.raw.manifest else None

    def report_state(self, instance, state) -> None:
        if self.report_down:
            raise SourceUnavailable("OSError")
        self.reports.append(state)


def config(tmp_path, mode="auto", **changes) -> LoaderConfig:
    fields = dict(
        service="backend",
        mode=mode,
        database_url="postgresql://u:p@localhost/db",
        master_key=MASTER,
        snapshot_dir=str(tmp_path / "snap"),
    )
    fields.update(changes)
    return LoaderConfig(**fields)


def runtime(tmp_path, source, mode="auto", env=None, required=(JWT,), now=None, **cfg):
    return SettingsRuntime(
        config(tmp_path, mode, **cfg),
        registry=default_registry(),
        source=source,
        required_env_keys=required,
        env={} if env is None else env,
        sleep=lambda s: None,
        now=now or (lambda: datetime.now(timezone.utc)),
    )


def tamper(raw: RawSnapshot, key: str) -> RawSnapshot:
    """The same snapshot with one row's signature broken."""
    rows = [replace(r, sig="0" * 64) if r.key == key else r for r in raw.rows]
    return RawSnapshot(rows, raw.manifest)


def hide(raw: RawSnapshot, key: str) -> RawSnapshot:
    """A view that withholds one row the manifest still lists."""
    return RawSnapshot([r for r in raw.rows if r.key != key], raw.manifest)


LATER = lambda days: (lambda: datetime.now(timezone.utc) + timedelta(days=days))  # noqa: E731
__all__ = [n for n in dir() if not n.startswith("_")] + ["plain_row"]
