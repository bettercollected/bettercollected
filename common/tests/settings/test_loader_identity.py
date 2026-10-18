"""Stable report instance id and the start-up warning of unset critical settings."""

import logging
import re
import stat

import pytest
from loader_support import JWT, PLANTED, FakeSource, jwt_row, make_keys, plain_row, raw_of, runtime

from common.settings.loader import reset
from common.settings.loader.source import instance_id


@pytest.fixture(autouse=True)
def _reset():
    reset()
    yield
    reset()


def good(keys):
    return raw_of(keys, [jwt_row(keys), plain_row(value=1, section="limits", readers=("backend",), key="API_ALLOWED_WORKSPACES")], 1)


def test_instance_id_is_stable_per_container_and_valid(monkeypatch):
    monkeypatch.setattr("socket.gethostname", lambda: "3f9c1d2ab7e4")
    assert instance_id("backend") == instance_id("backend") == "backend:3f9c1d2ab7e4"
    monkeypatch.setattr("socket.gethostname", lambda: "host name/with*odd" + "x" * 80)
    assert re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", instance_id("backend"))


def test_instance_id_without_a_hostname_persists_a_random_id(monkeypatch, tmp_path):
    monkeypatch.setattr("socket.gethostname", lambda: "localhost")
    d = str(tmp_path / "ids")
    first = instance_id("auth", d)
    assert first == instance_id("auth", d) and first.startswith("auth:")
    assert stat.S_IMODE((tmp_path / "ids" / "instance-auth").stat().st_mode) == 0o600
    assert instance_id("auth") != instance_id("auth")  # no directory: per process


def test_reports_use_the_stable_instance_id(tmp_path, monkeypatch):
    seen = []

    class Rec(FakeSource):
        def report_state(self, instance, state):
            seen.append(instance)

    monkeypatch.setattr("socket.gethostname", lambda: "abc123")
    rt = runtime(tmp_path, Rec(good(make_keys())))
    rt.start()
    rt.report()
    rt.report()
    assert seen == ["backend:abc123"] * 2


def test_startup_warns_once_with_names_only(tmp_path, caplog):
    caplog.set_level(logging.WARNING)
    rt = runtime(tmp_path, FakeSource(good(make_keys())), env={"AUTH_AES_HEX_KEY": PLANTED})
    rt.start()
    warnings = [r.getMessage() for r in caplog.records if "no value from the environment" in r.getMessage()]
    assert len(warnings) == 1
    assert "SSO_POLIS_API_KEY" in warnings[0]
    # AUTH_JWT_SECRET has a store row and AUTH_AES_HEX_KEY an env value
    assert JWT not in warnings[0] and "AUTH_AES_HEX_KEY" not in warnings[0]
    assert PLANTED not in caplog.text
