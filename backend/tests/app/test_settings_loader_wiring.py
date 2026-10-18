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


class MailLike(StoreBackedSettings):
    SMTP_PORT: int = 587
    SMTP_SERVER: str = "localhost"
    PASSWORD: str = ""
    model_config = SettingsConfigDict(env_prefix="MAIL_")


def rows(keys):
    plain = SettingRow(
        "MAIL_SMTP_PORT", "mail", ("backend", "auth"), False, "R", 1, NOW, value=2525
    )
    server = SettingRow(
        "MAIL_SMTP_SERVER", "mail", ("backend", "auth"), False, "R", 1, NOW, value="smtp.example.org"
    )
    secret = SettingRow(
        "MAIL_PASSWORD", "mail", ("backend", "auth"), True, "R", 1, NOW,
        blob=keys.seal("mail", "MAIL_PASSWORD", 1, "store-password"),
    )
    snap = FakeSnapshot.build([plain, server, secret], keys, 1)
    return RawSnapshot(list(snap.row_list), snap.signed_manifest)


@pytest.fixture
def store(monkeypatch, tmp_path):
    keys = SectionKeys(MASTER, sections=["mail"])
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
    monkeypatch.delenv("MAIL_SMTP_PORT", raising=False)
    assert MailLike().SMTP_PORT == 587
    # exactly pydantic-settings' own source list, in its own order
    assert MailLike.settings_customise_sources(MailLike, 1, 2, 3, 4) == (1, 2, 3, 4)


def test_environment_beats_store_and_store_beats_default(store, monkeypatch):
    monkeypatch.delenv("MAIL_SMTP_PORT", raising=False)
    monkeypatch.delenv("MAIL_PASSWORD", raising=False)
    monkeypatch.setenv("MAIL_SMTP_SERVER", "env.example.org")
    store.env = {"MAIL_SMTP_SERVER": "env.example.org"}
    mail = MailLike()
    assert mail.SMTP_SERVER == "env.example.org"
    assert mail.SMTP_PORT == 2525
    assert mail.PASSWORD == "store-password"


def test_an_empty_environment_value_does_not_shadow_the_store(store, monkeypatch):
    monkeypatch.setenv("MAIL_SMTP_PORT", "")
    monkeypatch.setenv("MAIL_PASSWORD", "  ")
    store.env = {"MAIL_SMTP_PORT": "", "MAIL_PASSWORD": "  "}
    mail = MailLike()
    assert (mail.SMTP_PORT, mail.PASSWORD) == (2525, "store-password")


def test_a_setting_without_a_store_row_keeps_its_default_and_empty_env_semantics(store, monkeypatch):
    class Other(StoreBackedSettings):
        UNSPLASH_ACCESS_KEY: str = "dflt"
        model_config = SettingsConfigDict()

    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "")
    assert Other().UNSPLASH_ACCESS_KEY == ""  # unchanged behaviour outside the store
