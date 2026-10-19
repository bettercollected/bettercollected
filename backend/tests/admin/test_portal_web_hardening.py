"""Response headers, pre-login form tokens, and the mail password pinned to its
transport settings."""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport

from backend.admin import headers as hdr
from backend.admin.asgi import get_admin_application
from backend.admin.gate.settings import GateSettings
from backend.admin.security import csrf
from backend.admin.security.clock import FakeClock
from tests.admin.conftest import needs_postgres
from tests.admin.test_setup_wizard import (
    MAIL_FORM,
    save_mail,
    start_mail,
    to_enrolled,
)

KEY = b"k" * 32


# -- headers -------------------------------------------------------------------------


def test_permissions_policy_denies_the_powerful_features():
    value = dict(hdr.SECURITY_HEADERS)[b"permissions-policy"].decode()
    for feature in ("camera", "microphone", "geolocation", "payment", "usb"):
        assert f"{feature}=()" in value
    assert value.strip()


def test_hsts_is_added_only_when_asked_and_replaces_a_handler_value():
    plain = dict(hdr.with_security_headers([]))
    assert b"strict-transport-security" not in plain
    tls = hdr.with_security_headers([(b"Strict-Transport-Security", b"max-age=1")], https=True)
    values = [v for k, v in tls if k == b"strict-transport-security"]
    assert values == [hdr.HSTS[1]] and b"max-age=31536000" in values[0]


async def _headers(app, peer: str, scheme: str, extra=None):
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app, client=(peer, 40000)),
        base_url=f"{scheme}://localhost:8100",
    ) as client:
        return (await client.get("/login", headers=extra or {})).headers


@needs_postgres
async def test_hsts_follows_the_request_scheme_and_trusted_proxies(portal):
    plain = get_admin_application(GateSettings.from_env({}), portal=portal)
    assert "strict-transport-security" not in await _headers(plain, "127.0.0.1", "http")
    assert "strict-transport-security" in await _headers(plain, "127.0.0.1", "https")
    # a forwarded header from anyone who is not a trusted proxy is ignored
    spoof = {"x-forwarded-proto": "https"}
    assert "strict-transport-security" not in await _headers(plain, "127.0.0.1", "http", spoof)
    proxied = get_admin_application(
        GateSettings.from_env({"ADMIN_TRUSTED_PROXIES": "127.0.0.1"}), portal=portal
    )
    assert "strict-transport-security" in await _headers(proxied, "127.0.0.1", "http", spoof)
    http_only = {"x-forwarded-proto": "http"}
    assert "strict-transport-security" not in await _headers(proxied, "127.0.0.1", "http", http_only)


@needs_postgres
async def test_permissions_policy_is_sent_with_a_value(portal):
    app = get_admin_application(GateSettings.from_env({}), portal=portal)
    value = (await _headers(app, "127.0.0.1", "https"))["permissions-policy"]
    assert "camera=()" in value


# -- pre-login form token ----------------------------------------------------------


def test_pre_login_form_token_expires_after_fifteen_minutes():
    assert csrf.FORM_TOKEN_MAX_AGE == 900
    clock = FakeClock(10_000)
    token = csrf.issue_form_token(KEY, clock)
    clock.advance(899)
    assert csrf.verify_form_token(KEY, token, token, clock)
    clock.advance(2)
    assert not csrf.verify_form_token(KEY, token, token, clock)


# -- the saved mail password is pinned to the transport settings -------------------------


@needs_postgres
@pytest.mark.parametrize(
    "change",
    [
        {"validate_certs": "false"},  # certificates no longer checked
        {"starttls": "false", "ssl_tls": "false"},  # clear text
    ],
)
async def test_a_saved_password_needs_retyping_when_the_transport_gets_weaker(
    app, runtime_engine, clock, transport, change
):
    b, *_ = await to_enrolled(app, runtime_engine, clock)
    await save_mail(b, transport)
    sent = len(transport.sent)
    r = await start_mail(b, password="", **change)
    assert r.status_code == 400 and "type the password again" in r.text
    assert MAIL_FORM["password"] not in r.text
    assert len(transport.sent) == sent  # nothing was sent, in clear or anywhere
    # typing the password again is the explicit decision
    assert (await start_mail(b, password="another-long-secret-8", **change)).status_code == 200
    await b.aclose()


@needs_postgres
async def test_a_saved_password_follows_a_stronger_transport_and_an_unchanged_insecure_one(
    app, runtime_engine, clock, transport
):
    b, *_ = await to_enrolled(app, runtime_engine, clock)
    # saved over an insecure transport on purpose (the password was typed with it)
    weak = {"starttls": "false", "ssl_tls": "false", "validate_certs": "false"}
    coded = await start_mail(b, **weak)
    assert coded.status_code == 200
    import re

    from tests.admin.test_setup_wizard import SIX, csrf_from

    code = SIX.search(transport.sent[-1].body).group(1)
    blob = re.search(r'name="pending" value="([^"]+)"', coded.text).group(1)
    ok = await b.post(
        "/setup/mail/confirm",
        data={"csrf_token": csrf_from(coded), "pending": blob, "mail_code": code},
    )
    assert ok.status_code == 303
    # unchanged: the saved password may be used again
    assert (await start_mail(b, password="", **weak)).status_code == 200
    # a different insecure combination is not "unchanged"
    other = {"starttls": "true", "ssl_tls": "false", "validate_certs": "false"}
    assert (await start_mail(b, password="", **other)).status_code == 400
    # a protected, verified transport may always carry it (same server, port, user)
    assert (await start_mail(b, password="")).status_code == 200
    await b.aclose()
