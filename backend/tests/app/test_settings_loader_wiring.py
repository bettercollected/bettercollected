"""The settings loader as wired into the backend: off in tests, and the
pydantic-settings source order when a store is on."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from common.settings.canonical import SettingRow
from common.settings.keys import SectionKeys
from common.settings.loader import LoaderConfig, SettingsRuntime, runtime as runtime_module
from common.settings.loader.pydantic_source import StoreBackedSettings
from common.settings.loader.source import RawSnapshot
from common.settings.registry import default_registry
from common.settings.snapshot import FakeSnapshot
from pydantic_settings import SettingsConfigDict

MASTER = base64.b64encode(bytes(range(48))).decode()
NOW = datetime(2026, 10, 18, tzinfo=timezone.utc)


class LimitsLike(StoreBackedSettings):
    ALLOWED_WORKSPACES: int = 5
    ALLOWED_COLLABORATORS: int = 3
    model_config = SettingsConfigDict(env_prefix="API_")


class KeysLike(StoreBackedSettings):
    JWT_SECRET: str = ""
    model_config = SettingsConfigDict(env_prefix="AUTH_")


def rows(keys):
    workspaces = SettingRow(
        "API_ALLOWED_WORKSPACES", "limits", ("backend",), False, "R", 1, NOW, value=25
    )
    collaborators = SettingRow(
        "API_ALLOWED_COLLABORATORS", "limits", ("backend",), False, "R", 1, NOW, value=9
    )
    secret = SettingRow(
        "AUTH_JWT_SECRET", "auth_keys", ("backend", "auth", "google"), True, "R", 1, NOW,
        blob=keys.seal("auth_keys", "AUTH_JWT_SECRET", 1, "store-jwt-secret"),
    )
    snap = FakeSnapshot.build([workspaces, collaborators, secret], keys, 1)
    return RawSnapshot(list(snap.row_list), snap.signed_manifest)


@pytest.fixture
def store(monkeypatch, tmp_path):
    keys = SectionKeys(MASTER, sections=["limits", "auth_keys"])
    source = SimpleNamespace(
        fetch=lambda: rows(keys), fetch_revision=lambda: 1, report_state=lambda *a: None
    )
    cfg = LoaderConfig(
        service="backend", mode="auto", database_url="postgresql://x/y",
        master_key=MASTER, snapshot_dir=str(tmp_path / "snap"),
    )
    rt = SettingsRuntime(cfg, registry=default_registry(), source=source, env={})
    rt.start()
    monkeypatch.setattr(runtime_module, "_runtime", rt)
    return rt


def test_the_loader_is_off_in_the_test_suite():
    import backend.config  # noqa: F401  (built at import time)

    assert runtime_module.current_runtime() is None


def test_with_the_store_off_the_default_sources_apply(monkeypatch):
    monkeypatch.delenv("API_ALLOWED_WORKSPACES", raising=False)
    assert LimitsLike().ALLOWED_WORKSPACES == 5
    # exactly pydantic-settings' own source list, in its own order
    assert LimitsLike.settings_customise_sources(LimitsLike, 1, 2, 3, 4) == (1, 2, 3, 4)


def test_environment_beats_store_and_store_beats_default(store, monkeypatch):
    monkeypatch.delenv("API_ALLOWED_WORKSPACES", raising=False)
    monkeypatch.delenv("AUTH_JWT_SECRET", raising=False)
    monkeypatch.setenv("API_ALLOWED_COLLABORATORS", "4")
    store.env = {"API_ALLOWED_COLLABORATORS": "4"}
    limits = LimitsLike()
    assert limits.ALLOWED_COLLABORATORS == 4
    assert limits.ALLOWED_WORKSPACES == 25
    assert KeysLike().JWT_SECRET == "store-jwt-secret"


def test_an_empty_environment_value_does_not_shadow_the_store(store, monkeypatch):
    monkeypatch.setenv("API_ALLOWED_WORKSPACES", "")
    monkeypatch.setenv("AUTH_JWT_SECRET", "  ")
    store.env = {"API_ALLOWED_WORKSPACES": "", "AUTH_JWT_SECRET": "  "}
    assert LimitsLike().ALLOWED_WORKSPACES == 25
    assert KeysLike().JWT_SECRET == "store-jwt-secret"


def test_a_setting_without_a_store_row_keeps_its_default_and_empty_env_semantics(store, monkeypatch):
    class Other(StoreBackedSettings):
        UNSPLASH_ACCESS_KEY: str = "dflt"
        model_config = SettingsConfigDict()

    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "")
    assert Other().UNSPLASH_ACCESS_KEY == ""  # unchanged behaviour outside the store
