"""Hot keys and restart_pending, unusable secrets."""

import logging

import pytest
from loader_support import JWT, PLANTED, FakeSource, jwt_row, make_keys, raw_of, rate_row, runtime

from common.settings.canonical import SettingRow
from common.settings.loader import StoreError, reset
from common.settings.loader import runtime as runtime_module
from common.settings.loader.proven import LIVE_PROVEN
from common.settings.registry import Reload, default_registry

RATE = "API_FLOW_EVENTS_PER_WINDOW"


@pytest.fixture(autouse=True)
def _reset():
    reset()
    yield
    reset()


def test_every_hot_key_in_the_registry_is_a_proven_live_consumer():
    hot = {s.key for s in default_registry() if s.reload_class is Reload.H}
    assert hot == set(LIVE_PROVEN)


def test_a_hot_key_with_a_proven_consumer_needs_no_restart(tmp_path):
    keys = make_keys()
    source = FakeSource(raw_of(keys, [rate_row(1, version=1)], 1))
    rt = runtime(tmp_path, source, env={})
    rt.start()
    source.raw = raw_of(keys, [rate_row(2, version=2)], 2)
    rt.poll_once()
    assert RATE in LIVE_PROVEN and rt.restart_pending is False


def test_a_hot_key_without_a_proven_consumer_reports_restart_pending(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime_module, "LIVE_PROVEN", frozenset())
    keys = make_keys()
    source = FakeSource(raw_of(keys, [rate_row(1, version=1)], 1))
    rt = runtime(tmp_path, source, env={})
    rt.start()
    source.raw = raw_of(keys, [rate_row(2, version=2)], 2)
    rt.poll_once()
    assert rt.restart_pending is True and source.reports[-1].restart_pending is True


def _unusable_secret(keys):
    row = jwt_row(keys)
    broken = SettingRow(
        key=row.key, section=row.section, readers=row.readers, is_secret=True,
        reload_class="R", version=row.version, updated_at=row.updated_at,
        blob="v2:not-a-real-envelope",
    )
    return raw_of(keys, [broken], 1)


def test_an_unusable_stored_secret_is_refused_and_logged_once_in_auto_mode(tmp_path, caplog):
    caplog.set_level(logging.WARNING)
    rt = runtime(tmp_path, FakeSource(_unusable_secret(make_keys())), env={})
    rt.start()
    assert rt.resolve_key(JWT) is None and rt.resolve_key(JWT) is None
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1 and JWT in errors[0].getMessage()
    assert PLANTED not in caplog.text and "v2:not-a-real" not in caplog.text


def test_an_unusable_stored_secret_stops_a_required_service(tmp_path):
    rt = runtime(tmp_path, FakeSource(_unusable_secret(make_keys())), mode="required", env={})
    rt.start()
    with pytest.raises(StoreError, match=JWT):
        rt.resolve_key(JWT)


def test_the_environment_value_is_kept_when_the_stored_secret_is_unusable(tmp_path):
    rt = runtime(tmp_path, FakeSource(_unusable_secret(make_keys())), env={JWT: "from-env"})
    rt.start()
    assert rt.resolve_key(JWT) is None  # the environment is the source
