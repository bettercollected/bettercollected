"""The keyset fingerprint a service reports comes from the resolved keyset: the
environment, else the store's verified row."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.config.application import keyset_key_ids
from common.services.keyset import add_primary_key, encode_keyset
from common.settings.canonical import SettingRow
from common.settings.keys import SectionKeys
from common.settings.loader import (
    LoaderConfig,
    SettingsRuntime,
    keyset_fingerprint,
    set_keyset_key_ids,
)
from common.settings.loader import runtime as runtime_module
from common.settings.loader.source import RawSnapshot
from common.settings.registry import default_registry
from common.settings.snapshot import FakeSnapshot
from tink.proto import tink_pb2

MASTER = base64.b64encode(bytes(range(48))).decode()
KEYSET = "MASTER_ENCRYPTION_KEYSET"


def _store(monkeypatch, tmp_path, encoded):
    keys = SectionKeys(MASTER, sections=["auth_keys"])
    spec = default_registry().get(KEYSET)
    row = SettingRow(
        KEYSET, spec.section, spec.readers, True, spec.reload_class.value, 1,
        datetime(2026, 10, 18, tzinfo=timezone.utc),
        blob=keys.seal(spec.section, KEYSET, 1, encoded),
    )
    snap = FakeSnapshot.build([row], keys, 1)
    raw = RawSnapshot(list(snap.row_list), snap.signed_manifest)
    source = SimpleNamespace(fetch=lambda: raw, fetch_revision=lambda: 1, report_state=lambda *a: None)
    cfg = LoaderConfig(
        service="backend", mode="auto", database_url="postgresql://x/y",
        master_key=MASTER, snapshot_dir=str(tmp_path / "snap"),
    )
    rt = SettingsRuntime(cfg, registry=default_registry(), source=source, env={})
    rt.start()
    monkeypatch.setattr(runtime_module, "_runtime", rt)
    return rt


def test_a_store_only_keyset_reports_its_own_fingerprint(monkeypatch, tmp_path):
    keyset = add_primary_key(tink_pb2.Keyset())
    encoded = encode_keyset(keyset)
    ids = [k.key_id for k in keyset.key]
    monkeypatch.delenv(KEYSET, raising=False)
    rt = _store(monkeypatch, tmp_path, encoded)
    assert keyset_key_ids() == ids
    set_keyset_key_ids(keyset_key_ids)
    try:
        assert rt.state().keyset_fp == keyset_fingerprint(ids)
        assert str(ids[0]) not in rt.state().keyset_fp and encoded not in rt.state().keyset_fp
    finally:
        set_keyset_key_ids(None)


def test_the_environment_keyset_wins_over_the_store(monkeypatch, tmp_path):
    env_keyset = add_primary_key(tink_pb2.Keyset())
    store_keyset = add_primary_key(tink_pb2.Keyset())
    _store(monkeypatch, tmp_path, encode_keyset(store_keyset))
    monkeypatch.setenv(KEYSET, encode_keyset(env_keyset))
    assert keyset_key_ids() == [k.key_id for k in env_keyset.key]
