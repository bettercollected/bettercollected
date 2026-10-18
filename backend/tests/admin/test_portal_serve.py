"""``serve.build_app``: the bare gate without the portal's settings, the portal with them."""

import base64
import logging

import pytest

from backend.admin.config import AdminConfigError
from backend.admin.portal_config import missing_portal_settings
from backend.admin.serve import build_app
from tests.admin.test_gate import call

KEY = base64.b64encode(bytes(range(48))).decode()
SECRET_URL = "postgresql://bc_admin:hunter2-secret@db.internal:5432/x"
FULL = {
    "ADMIN_DATABASE_URL": SECRET_URL,
    "SETTINGS_MASTER_KEY": KEY,
    "PLATFORM_ADMIN_EMAILS": "ops@example.org",
}


def warnings(caplog):
    return [r for r in caplog.records if r.levelno == logging.WARNING and r.name == "backend.admin"]


async def test_without_settings_it_serves_only_the_health_check(caplog):
    caplog.set_level(logging.WARNING)
    app = build_app({})
    assert not hasattr(app.inner.state, "portal")
    status, _, body = await call(app, path="/healthz")  # what the container healthcheck reads
    assert (status, body) == (200, b"ok")
    for path in ("/login", "/login/code", "/mfa", "/", "/api/me", "/static/admin.css"):
        assert (await call(app, path=path))[0] == 404, path
    (record,) = warnings(caplog)
    text = record.getMessage()
    for name in ("ADMIN_DATABASE_URL", "SETTINGS_MASTER_KEY", "PLATFORM_ADMIN_EMAILS"):
        assert name in text


@pytest.mark.parametrize("drop", ["ADMIN_DATABASE_URL", "SETTINGS_MASTER_KEY", "PLATFORM_ADMIN_EMAILS"])
async def test_any_missing_setting_means_skeleton_and_values_are_never_logged(drop, caplog):
    caplog.set_level(logging.WARNING)
    env = {k: v for k, v in FULL.items() if k != drop}
    app = build_app(env)
    assert (await call(app, path="/healthz"))[0] == 200
    assert (await call(app, path="/login"))[0] == 404
    (record,) = warnings(caplog)
    assert drop in record.getMessage()
    assert "hunter2" not in caplog.text and KEY not in caplog.text and "ops@example" not in caplog.text


def test_an_admin_list_without_a_valid_address_counts_as_missing():
    assert missing_portal_settings({**FULL, "PLATFORM_ADMIN_EMAILS": " , junk"}) == ["PLATFORM_ADMIN_EMAILS"]
    assert missing_portal_settings(FULL) == []


async def test_with_everything_it_builds_the_portal_and_still_answers_health(caplog):
    caplog.set_level(logging.WARNING)
    app = build_app(FULL)
    assert app.inner.state.portal is not None
    assert (await call(app, path="/healthz"))[0] == 200
    status, headers, body = await call(app, path="/login")
    assert status == 200 and b"Send code" in body
    assert warnings(caplog) == []


def test_a_present_but_invalid_master_key_stops_startup():
    with pytest.raises(AdminConfigError):
        build_app({**FULL, "SETTINGS_MASTER_KEY": "short"})
