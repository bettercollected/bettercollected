"""The first-run setup wizard on real Postgres: reachability, the token, step
order, mail confirmation, lock-out after enrolment, and no secret anywhere."""

from __future__ import annotations

import json
import re
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import text

from backend.admin import cookies
from backend.admin.controllers.portal import build_registry
from backend.admin.gate.levels import Level, RouteRegistry, SetupStage
from backend.admin.gate.stepup import require_stepup
from backend.admin.security import totp
from backend.admin.security.keys import parse_master_key
from backend.admin.services import setup_token
from tests.admin.conftest import MASTER_KEY, needs_postgres
from tests.admin.portal_fixtures import ADMIN, OTHER_ADMIN, TOKEN_RE, UA, Browser, sign_in
from tests.admin.test_portal_mfa import CODES_RE, FACTOR_RE, SECRET_RE, enrol_direct

pytestmark = needs_postgres

MASTER = parse_master_key(MASTER_KEY)
REFUSED = "/setup?failed=1"
MAIL_FORM = {
    "server": "smtp.example.org",
    "port": "587",
    "sender": "admin@example.org",
    "user": "mailer",
    "password": "correct-horse-battery-staple-7",
    "starttls": "true",
    "ssl_tls": "false",
    "use_credentials": "true",
    "validate_certs": "true",
}
SIX = re.compile(r"confirmation code is (\d{6})")


async def rows(engine, sql, **params):
    async with engine.connect() as conn:
        return (await conn.execute(text(sql), params)).all()


async def audit_text(engine) -> str:
    out = await rows(
        engine,
        "SELECT action, actor_kind, actor_email, target_type, target_id, outcome, "
        "before::text, after::text, detail::text FROM admin.audit_log ORDER BY seq",
    )
    return json.dumps([list(map(str, r)) for r in out])


async def actions(engine):
    return [r[0] for r in await rows(engine, "SELECT action FROM admin.audit_log ORDER BY seq")]


async def issue(engine) -> str:
    async with engine.begin() as conn:
        token, _ = await setup_token.issue(conn, MASTER, "tester")
    return token


async def redeem(b: Browser, token: str, email: str = ADMIN, form=None, **kw):
    """Post the token form; ``form="kept"`` reuses the form token of an earlier page
    (the page itself is gone once setup is closed)."""
    if form == "kept":
        csrf = b.__dict__.setdefault("_kept_form", None)
    else:
        csrf = await b.form_token("/setup")
        b.__dict__["_kept_form"] = csrf
    return await b.post(
        "/setup", data={"token": token, "email": email, "csrf_token": csrf}, **kw
    )


async def to_enrolled(app, runtime_engine, clock):
    """Token -> setup session -> TOTP enrolled through the portal's own pages.
    Returns (browser, token, secret, recovery codes)."""
    token = await issue(runtime_engine)
    b = Browser(app)
    response = await redeem(b, token)
    assert response.status_code == 303 and response.headers["location"] == "/mfa/enrol"
    page = await b.get("/mfa/enrol")
    csrf = TOKEN_RE.search(page.text).group(1)
    started = await b.post("/mfa/enrol", data={"csrf_token": csrf})
    secret = SECRET_RE.search(started.text).group(1).replace(" ", "")
    factor_id = FACTOR_RE.search(started.text).group(1)
    done = await b.post(
        "/mfa/enrol/confirm",
        data={
            "csrf_token": csrf, "factor_id": factor_id,
            "code": totp.code_at(secret, clock.time()),
        },
    )
    assert done.status_code == 200
    codes = CODES_RE.findall(done.text)
    assert len(codes) == 10
    return b, token, secret, codes, done


def csrf_from(page) -> str:
    return TOKEN_RE.search(page.text).group(1)


async def start_mail(b: Browser, **overrides):
    page = await b.get("/setup/mail")
    assert page.status_code == 200
    data = {**MAIL_FORM, **overrides, "csrf_token": csrf_from(page)}
    return await b.post("/setup/mail/test", data=data)


# -- unreachable without a token ---------------------------------------------------


async def test_setup_is_a_bare_404_without_a_token(app, browser):
    assert (await browser.get("/setup")).status_code == 404
    assert (await browser.get("/setup")).content == b""
    # a post without the form token never reaches the handler
    assert (await browser.post("/setup", data={"token": "x", "email": ADMIN})).status_code == 403
    for path in ("/setup/mail", "/setup/finish", "/setup/mail/test", "/setup/mail/confirm"):
        assert (await browser.get(path)).status_code == 404


async def test_the_page_appears_with_a_valid_token_and_disappears_when_it_expires(
    app, browser, runtime_engine, owner_engine
):
    await issue(runtime_engine)
    page = await browser.get("/setup")
    assert page.status_code == 200 and 'name="token" type="password"' in page.text
    assert "no-store" in page.headers["cache-control"]
    async with owner_engine.begin() as conn:
        await conn.execute(text("UPDATE admin.setup_tokens SET expires_at = now() - interval '1 minute'"))
    assert (await browser.get("/setup")).status_code == 404


# -- the whole path --------------------------------------------------------------------


async def test_the_full_wizard_and_it_closes_for_good(
    app, portal, transport, clock, runtime_engine
):
    b, token, secret, codes, done = await to_enrolled(app, runtime_engine, clock)
    # the enrolment machinery is the existing one: the token page is gone as soon as a
    # factor is confirmed, and the session is a normal signed-in one
    assert (await b.get("/api/me")).json()["mfa_state"] == "mfa_ok"
    assert (await Browser(app).get("/setup")).status_code == 404
    state = (await rows(runtime_engine, "SELECT started_by, completed_at, mail_step FROM admin.setup_state"))[0]
    assert state == (ADMIN, None, None)

    # "Continue" on the recovery codes leads into the wizard
    saved = await b.post(
        "/mfa/recovery-codes/saved", data={"csrf_token": csrf_from(done), "saved": "yes"}
    )
    assert saved.status_code == 303 and saved.headers["location"] == "/setup/mail"
    # finishing is not possible before the mail step is decided
    page = await b.get("/setup/finish")
    assert page.status_code == 303 and page.headers["location"] == "/setup/mail"

    sent_before = len(transport.sent)
    coded = await start_mail(b)
    assert coded.status_code == 200 and "Confirm the test mail" in coded.text
    # nothing is saved yet
    assert (await rows(runtime_engine, "SELECT count(*) FROM settings.entries WHERE key LIKE 'ADMIN_MAIL_%'"))[0][0] == 0
    assert transport.recipients[-1] == ADMIN
    mail_code = SIX.search(transport.sent[-1].body).group(1)
    assert len(transport.sent) == sent_before + 1
    blob = re.search(r'name="pending" value="([^"]+)"', coded.text).group(1)
    assert MAIL_FORM["password"] not in coded.text and mail_code not in coded.text
    assert MAIL_FORM["password"] not in blob

    # a wrong code saves nothing
    wrong = await b.post(
        "/setup/mail/confirm",
        data={"csrf_token": csrf_from(coded), "pending": blob, "mail_code": "000000" if mail_code != "000000" else "111111"},
    )
    assert wrong.status_code == 200 and "That code was not accepted" in wrong.text
    assert (await rows(runtime_engine, "SELECT count(*) FROM settings.entries WHERE key LIKE 'ADMIN_MAIL_%'"))[0][0] == 0

    ok = await b.post(
        "/setup/mail/confirm",
        data={"csrf_token": csrf_from(coded), "pending": blob, "mail_code": mail_code},
    )
    assert ok.status_code == 303 and ok.headers["location"] == "/setup/finish"
    keys = {r[0] for r in await rows(runtime_engine, "SELECT key FROM settings.entries WHERE key LIKE 'ADMIN_MAIL_%'")}
    assert keys == {
        "ADMIN_MAIL_SMTP_SERVER", "ADMIN_MAIL_SMTP_PORT", "ADMIN_MAIL_SENDER", "ADMIN_MAIL_USER",
        "ADMIN_MAIL_PASSWORD", "ADMIN_MAIL_STARTTLS", "ADMIN_MAIL_SSL_TLS",
        "ADMIN_MAIL_USE_CREDENTIALS", "ADMIN_MAIL_VALIDATE_CERTS",
    }
    # the portal's mail now comes from the saved settings
    assert portal.setup.mail_source() == "store"

    final = await b.get("/setup/finish")
    assert final.status_code == 200
    fingerprint = portal.setup.fingerprint
    assert fingerprint in final.text and MASTER_KEY not in final.text
    # no acknowledgement, no finish
    refused = await b.post("/setup/finish", data={"csrf_token": csrf_from(final)})
    assert refused.status_code == 400 and "Tick the box" in refused.text
    before = len(transport.sent)
    finished = await b.post("/setup/finish", data={"csrf_token": csrf_from(final), "ack": "yes"})
    assert finished.status_code == 303 and finished.headers["location"] == "/"
    assert len(transport.sent) > before  # every admin was told

    # closed for good: even the signed-in admin who did it cannot reach any step
    for path in ("/setup", "/setup/mail", "/setup/finish"):
        assert (await b.get(path)).status_code == 404
    state = (await rows(runtime_engine, "SELECT completed_at IS NOT NULL, mail_step FROM admin.setup_state"))[0]
    assert tuple(state) == (True, "saved")
    log = await actions(runtime_engine)
    for name in (
        "setup.token_redeemed", "mfa.enrolled", "setup.mail_test", "settings.set",
        "setup.mail_saved", "setup.completed",
    ):
        assert name in log, name
    # the dashboard has no setup banner any more
    assert "first-run setup is not finished" not in (await b.get("/")).text

    # no secret in any audit row
    everything = await audit_text(runtime_engine)
    for secret_value in (token, setup_token.display(token), mail_code, MAIL_FORM["password"], secret, *codes):
        assert secret_value not in everything
    await b.aclose()


async def test_the_dashboard_offers_the_unfinished_setup(app, runtime_engine, clock):
    b, *_ = await to_enrolled(app, runtime_engine, clock)
    assert "first-run setup is not finished" in (await b.get("/")).text
    await b.aclose()


async def test_skipping_mail_then_finishing(app, runtime_engine, clock):
    b, *_ = await to_enrolled(app, runtime_engine, clock)
    page = await b.get("/setup/mail")
    skipped = await b.post("/setup/mail/skip", data={"csrf_token": csrf_from(page)})
    assert skipped.headers["location"] == "/setup/finish"
    final = await b.get("/setup/finish")
    assert "Skipped." in final.text
    await b.post("/setup/finish", data={"csrf_token": csrf_from(final), "ack": "yes"})
    assert (await b.get("/setup/finish")).status_code == 404
    assert (await rows(runtime_engine, "SELECT count(*) FROM settings.entries WHERE key LIKE 'ADMIN_MAIL_%'"))[0][0] == 0
    assert "setup.mail_skipped" in await actions(runtime_engine)
    await b.aclose()


# -- the token: replay, expiry, lock, limits ------------------------------------------


async def test_a_token_works_once(app, runtime_engine):
    token = await issue(runtime_engine)
    second = Browser(app)
    form = await second.form_token("/setup")  # a form token taken while the page was open
    first = Browser(app)
    assert (await redeem(first, token)).status_code == 303
    # the page is gone (nothing left to redeem) and a replay is refused like any other try
    assert (await second.get("/setup")).status_code == 404
    replay = await second.post("/setup", data={"token": token, "email": ADMIN, "csrf_token": form})
    assert replay.status_code == 303 and replay.headers["location"] == REFUSED
    sessions = await rows(runtime_engine, "SELECT mfa_state FROM admin.sessions")
    assert [r[0] for r in sessions] == ["setup"]


async def test_wrong_token_and_wrong_address_look_alike(app, runtime_engine):
    token = await issue(runtime_engine)
    b = Browser(app)
    wrong_token = await redeem(b, "AAAA-BBBB-CCCC-DDDD-EEEE-FFFF-GGGG-HHHH")
    unlisted = await redeem(b, token, "stranger@example.org")
    for r in (wrong_token, unlisted):
        assert r.status_code == 303 and r.headers["location"] == REFUSED and r.content == b""
    page = await b.get(REFUSED)
    assert "was not accepted" in page.text and "AAAA-BBBB" not in page.text
    # the right token with an unlisted address was not consumed; both tries counted against it
    attempts = (await rows(runtime_engine, "SELECT failed_attempts, consumed_at FROM admin.setup_tokens"))[0]
    assert tuple(attempts) == (2, None)
    assert (await redeem(b, setup_token.display(token).lower())).status_code == 303  # dashes, case are free
    assert (await b.get("/mfa/enrol")).status_code == 200


async def test_five_tries_per_address_then_even_the_right_token_is_refused(
    app, runtime_engine, clock
):
    token = await issue(runtime_engine)
    b = Browser(app)
    for _ in range(5):
        assert (await redeem(b, "WRONGWRONGWRONGWRONGWRONGWRONGWRONG")).headers["location"] == REFUSED
    blocked = await redeem(b, token)
    assert blocked.headers["location"] == REFUSED
    assert (await rows(runtime_engine, "SELECT consumed_at FROM admin.setup_tokens"))[0][0] is None
    clock.advance(16 * 60)  # the window ended
    assert (await redeem(b, token)).status_code == 303


async def test_twenty_wrong_tries_lock_the_token_and_tell_the_admins(
    app, runtime_engine, clock, transport
):
    token = await issue(runtime_engine)
    b = Browser(app)
    for round_ in range(4):
        for _ in range(5):
            assert (await redeem(b, "WRONGWRONGWRONGWRONGWRONGWRONGWRONG")).headers["location"] == REFUSED
        clock.advance(16 * 60)
    # locked for good, the page is gone, the right token no longer works
    assert (await b.get("/setup")).status_code == 404
    assert (await redeem(b, token, form="kept")).headers["location"] == REFUSED
    locked = (await rows(runtime_engine, "SELECT locked_at IS NOT NULL, failed_attempts FROM admin.setup_tokens"))[0]
    assert tuple(locked) == (True, 20)
    log = await actions(runtime_engine)
    assert log.count("setup.token_locked") == 1 and "setup.token_refused" in log
    assert any("locked" in m.subject for m in transport.sent)
    assert sorted(set(transport.recipients[-2:])) == sorted([ADMIN, OTHER_ADMIN])


async def test_a_new_token_replaces_the_old_one(app, runtime_engine):
    old = await issue(runtime_engine)
    async with runtime_engine.begin() as conn:
        new, replaced = await setup_token.issue(conn, MASTER, "tester", replace=True)
    assert replaced
    b = Browser(app)
    assert (await redeem(b, old)).headers["location"] == REFUSED
    assert (await redeem(b, new)).status_code == 303


# -- who may be signed in by it ---------------------------------------------------------


async def test_the_session_is_short_and_only_for_the_setup_pages(
    app, runtime_engine, clock
):
    token = await issue(runtime_engine)
    b = Browser(app)
    await redeem(b, token)
    row = (await rows(runtime_engine, "SELECT mfa_state, abs_expires_at - created_at, idle_expires_at - created_at FROM admin.sessions"))[0]
    assert row[0] == "setup"
    assert row[1] == timedelta(minutes=60) and row[2] == timedelta(minutes=15)
    # reaches enrolment and sign-out ...
    assert (await b.get("/mfa")).headers["location"] == "/mfa/enrol"
    assert (await b.get("/mfa/enrol")).status_code == 200
    # ... and nothing else, whatever the route
    for path in ("/", "/settings", "/account", "/mfa/verify", "/mfa/stepup", "/audit", "/api/me"):
        response = await b.get(path)
        assert response.status_code in (303, 401), path
        assert response.headers.get("location", "/login") in ("/login", "/mfa"), path
    for path in ("/setup", "/setup/mail", "/setup/finish"):
        assert (await b.get(path)).status_code == 404, path
    # it idles out after 15 minutes
    clock.advance(16 * 60)
    assert (await b.get("/mfa/enrol")).status_code == 303
    await b.aclose()


async def test_a_setup_session_is_bound_to_address_and_browser(app, runtime_engine):
    token = await issue(runtime_engine)
    b = Browser(app)
    await redeem(b, token)
    other = Browser(app, ua="another-browser/2.0")
    other.cookies.update(b.cookies)
    assert (await other.get("/mfa/enrol")).status_code == 303
    assert (await b.get("/mfa/enrol")).status_code == 303  # revoked by the mismatch
    await b.aclose()
    await other.aclose()


async def test_the_setup_session_dies_when_someone_else_confirms_a_factor(
    app, portal, runtime_engine, clock
):
    token = await issue(runtime_engine)
    b = Browser(app)
    await redeem(b, token)
    await enrol_direct(portal, clock, email=OTHER_ADMIN)  # the e-mail code path, another admin
    assert (await b.get("/mfa/enrol")).status_code == 303
    assert (await Browser(app).get("/setup")).status_code == 404
    await b.aclose()


async def test_nobody_can_start_after_a_factor_exists(app, portal, runtime_engine, clock):
    await enrol_direct(portal, clock)
    async with runtime_engine.begin() as conn:
        with pytest.raises(setup_token.SetupTokenError):
            await setup_token.issue(conn, MASTER, "tester")
    # even a token row that exists (inserted before the enrolment) is dead
    async with runtime_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO admin.setup_tokens (token_mac, issued_by, expires_at) "
                "VALUES (decode(repeat('ab', 32), 'hex'), 'x', now() + interval '1 hour')"
            )
        )
    b = Browser(app)
    assert (await b.get("/setup")).status_code == 404
    assert (await redeem_raw(b)).status_code in (403, 404)  # no form token without the page


async def redeem_raw(b):
    return await b.post("/setup", data={"token": "AAAA", "email": ADMIN, "csrf_token": "x"})


# -- step order --------------------------------------------------------------------------


async def test_the_checklist_is_only_for_the_admin_who_did_the_setup(
    app, portal, clock, runtime_engine
):
    b, *_ = await to_enrolled(app, runtime_engine, clock)
    # another admin, fully signed in, gets the bare 404
    await enrol_direct(portal, clock, email=OTHER_ADMIN)
    # sign that admin in fully through the service instead of the pages
    token, session = await portal.sessions.create(OTHER_ADMIN, "127.0.0.1", UA, mfa_state="mfa_ok")
    full = Browser(app)
    full.cookies[cookies.SESSION_COOKIE] = token
    for path in ("/setup/mail", "/setup/finish"):
        assert (await full.get(path)).status_code == 404, path
    assert (await b.get("/setup/mail")).status_code == 200
    await b.aclose()


async def test_started_window(app, runtime_engine, owner_engine, clock):
    b, *_ = await to_enrolled(app, runtime_engine, clock)
    assert (await b.get("/setup/mail")).status_code == 200
    async with owner_engine.begin() as conn:
        await conn.execute(text("UPDATE admin.setup_state SET started_at = now() - interval '3 hours'"))
    clock.advance(3 * 3600)
    assert (await b.get("/setup/mail")).status_code == 404
    await b.aclose()


async def test_mail_confirm_needs_a_test_first_and_the_blob_cannot_be_forged(
    app, runtime_engine, clock, transport
):
    b, *_ = await to_enrolled(app, runtime_engine, clock)
    page = await b.get("/setup/mail")
    csrf = csrf_from(page)
    for blob in ("", "junk", "9999999999.AAAA.BBBB"):
        r = await b.post("/setup/mail/confirm", data={"csrf_token": csrf, "pending": blob, "mail_code": "123456"})
        assert r.status_code == 400 and "expired" in r.text
    coded = await start_mail(b)
    blob = re.search(r'name="pending" value="([^"]+)"', coded.text).group(1)
    code = SIX.search(transport.sent[-1].body).group(1)
    expiry, nonce, sealed = blob.split(".")
    flipped = sealed[:-2] + ("AA" if not sealed.endswith("AA") else "BB")
    r = await b.post(
        "/setup/mail/confirm",
        data={"csrf_token": csrf, "pending": f"{expiry}.{nonce}.{flipped}", "mail_code": code},
    )
    assert r.status_code == 400 and "expired" in r.text
    assert (await rows(runtime_engine, "SELECT count(*) FROM settings.entries WHERE key LIKE 'ADMIN_MAIL_%'"))[0][0] == 0
    await b.aclose()


async def test_a_mail_that_is_not_delivered_saves_nothing(app, runtime_engine, clock, transport):
    b, *_ = await to_enrolled(app, runtime_engine, clock)
    transport.fail = True
    r = await start_mail(b)
    assert r.status_code == 400 and "could not be delivered" in r.text
    assert MAIL_FORM["password"] not in r.text
    assert (await rows(runtime_engine, "SELECT count(*) FROM settings.entries WHERE key LIKE 'ADMIN_MAIL_%'"))[0][0] == 0
    last = (await rows(runtime_engine, "SELECT action, outcome FROM admin.audit_log WHERE action = 'setup.mail_test' ORDER BY seq DESC"))[0]
    assert tuple(last) == ("setup.mail_test", "failure")
    await b.aclose()


async def test_invalid_mail_settings_are_refused_before_any_mail(app, runtime_engine, clock, transport):
    b, *_ = await to_enrolled(app, runtime_engine, clock)
    sent = len(transport.sent)
    for overrides in (
        {"server": ""},
        {"server": "127.0.0.1"},
        {"port": "99999"},
        {"starttls": "true", "ssl_tls": "true"},
        {"use_credentials": "true", "user": ""},
    ):
        r = await start_mail(b, **overrides)
        assert r.status_code == 400, overrides
        assert 'class="error"' in r.text
        assert MAIL_FORM["password"] not in r.text
    assert len(transport.sent) == sent
    await b.aclose()


async def test_the_test_mail_is_rate_limited(app, runtime_engine, clock, transport):
    b, *_ = await to_enrolled(app, runtime_engine, clock)
    for _ in range(3):
        assert (await start_mail(b)).status_code == 200
    assert (await start_mail(b)).status_code == 429
    clock.advance(11 * 60)
    # (the step-up window passed too: the page asks for a fresh code instead)
    assert (await start_mail(b)).status_code in (200, 303)
    await b.aclose()


async def test_the_mail_step_needs_a_fresh_second_factor(app, runtime_engine, clock):
    b, *_ = await to_enrolled(app, runtime_engine, clock)
    clock.advance(6 * 60)  # past the 5-minute window (the session is 30 min idle)
    page = await b.get("/setup/mail")
    assert page.status_code == 200
    r = await b.post("/setup/mail/test", data={**MAIL_FORM, "csrf_token": csrf_from(page)})
    assert r.status_code == 303 and r.headers["location"].startswith("/mfa/stepup?next=/setup/mail")
    await b.aclose()


async def test_a_stale_stepup_at_confirm_can_be_renewed_with_a_code(
    app, runtime_engine, clock, transport
):
    b, token, secret, codes, done = await to_enrolled(app, runtime_engine, clock)
    coded = await start_mail(b)
    blob = re.search(r'name="pending" value="([^"]+)"', coded.text).group(1)
    code = SIX.search(transport.sent[-1].body).group(1)
    clock.advance(6 * 60)
    csrf = csrf_from(coded)
    need = await b.post("/setup/mail/confirm", data={"csrf_token": csrf, "pending": blob, "mail_code": code})
    assert need.status_code == 200 and "fresh code" in need.text
    bad = await b.post(
        "/setup/mail/confirm",
        data={"csrf_token": csrf, "pending": blob, "mail_code": code, "code": "000000"},
    )
    assert "Nothing was saved" in bad.text
    good = await b.post(
        "/setup/mail/confirm",
        data={
            "csrf_token": csrf, "pending": blob, "mail_code": code,
            "code": totp.code_at(secret, clock.time()),
        },
    )
    assert good.status_code == 303 and good.headers["location"] == "/setup/finish"
    await b.aclose()


# -- CSRF, gate -------------------------------------------------------------------------


async def test_csrf_and_origin_protect_every_wizard_post(app, runtime_engine, clock):
    token = await issue(runtime_engine)
    b = Browser(app)
    form = await b.form_token("/setup")
    data = {"token": token, "email": ADMIN}
    assert (await b.post("/setup", data={**data, "csrf_token": "forged"})).status_code == 403
    assert (await b.post("/setup", data=data)).status_code == 403
    assert (await b.post("/setup", data={**data, "csrf_token": form}, origin="https://evil.example")).status_code == 403
    assert (await b.post("/setup", data={**data, "csrf_token": form}, headers={"sec-fetch-site": "cross-site"})).status_code == 403
    assert (await rows(runtime_engine, "SELECT consumed_at FROM admin.setup_tokens"))[0][0] is None
    await b.aclose()


async def test_checklist_posts_need_the_session_csrf_token(app, runtime_engine, clock):
    b, *_ = await to_enrolled(app, runtime_engine, clock)
    for path in ("/setup/mail/test", "/setup/mail/skip", "/setup/mail/confirm", "/setup/finish"):
        r = await b.post(path, data={"csrf_token": "forged", **MAIL_FORM})
        assert r.status_code == 403, path
        r = await b.post(path, data=MAIL_FORM)
        assert r.status_code == 403, path
    await b.aclose()


async def test_the_address_and_host_gate_come_first(app, runtime_engine):
    await issue(runtime_engine)
    outsider = Browser(app, peer="203.0.113.9")
    assert (await outsider.get("/setup")).status_code == 404
    assert (await outsider.post("/setup", data={"token": "x"})).status_code == 404
    odd_host = Browser(app)
    r = await odd_host.get("/setup", headers={"host": "evil.example"})
    assert r.status_code == 404
    assert (await rows(runtime_engine, "SELECT count(*) FROM admin.sessions"))[0][0] == 0


async def test_no_secret_in_logs_or_responses(app, runtime_engine, clock, transport, caplog):
    import logging

    caplog.set_level(logging.DEBUG)
    token = await issue(runtime_engine)
    b = Browser(app)
    responses = [await b.get("/setup"), await redeem(b, "WRONG-TOKEN-VALUE-0000"), await redeem(b, token)]
    page = await b.get("/mfa/enrol")
    csrf = csrf_from(page)
    started = await b.post("/mfa/enrol", data={"csrf_token": csrf})
    secret = SECRET_RE.search(started.text).group(1).replace(" ", "")
    done = await b.post(
        "/mfa/enrol/confirm",
        data={
            "csrf_token": csrf, "factor_id": FACTOR_RE.search(started.text).group(1),
            "code": totp.code_at(secret, clock.time()),
        },
    )
    responses.append(done)
    coded = await start_mail(b)
    code = SIX.search(transport.sent[-1].body).group(1)
    responses.append(coded)
    blob = re.search(r'name="pending" value="([^"]+)"', coded.text).group(1)
    confirmed = await b.post(
        "/setup/mail/confirm",
        data={"csrf_token": csrf_from(coded), "pending": blob, "mail_code": code},
    )
    responses.append(confirmed)
    for response in responses:
        for secret_value in (token, setup_token.display(token)):
            assert secret_value not in response.text
            assert secret_value not in str(response.headers)
        assert MAIL_FORM["password"] not in response.text
        assert "location" not in response.headers or token not in response.headers["location"]
    for record in caplog.records:
        line = record.getMessage()
        for secret_value in (token, setup_token.display(token), code, MAIL_FORM["password"], blob, secret):
            assert secret_value not in line
    # the token is not in any URL the app answered for (no query strings used)
    assert all("?" not in r.url.path for r in responses)
    await b.aclose()


# -- the registry's default deny ---------------------------------------------------------


def test_every_setup_route_declares_its_stage_and_nothing_else_does():
    reg = build_registry()
    stages = {}
    for route in reg.router.routes:
        stage = getattr(route.endpoint, "admin_setup_stage", None)
        under = route.path == "/setup" or route.path.startswith("/setup/")
        assert (stage is not None) == under, route.path
        if stage is not None:
            stages[(route.path, tuple(sorted(route.methods)))] = stage
    assert stages[("/setup", ("GET",))] is SetupStage.OPEN
    assert stages[("/setup", ("POST",))] is SetupStage.ATTEMPT
    assert {s for s in stages.values()} == {SetupStage.OPEN, SetupStage.ATTEMPT, SetupStage.CHECKLIST}
    # the open stage is the only one below the session levels
    for route in reg.router.routes:
        stage = getattr(route.endpoint, "admin_setup_stage", None)
        if stage is SetupStage.CHECKLIST:
            assert route.endpoint.admin_level == Level.SECOND_FACTOR
        if stage in (SetupStage.OPEN, SetupStage.ATTEMPT):
            assert route.endpoint.admin_level == Level.ADDRESS


def test_the_registry_refuses_setup_routes_without_a_stage_and_stages_elsewhere():
    reg = RouteRegistry()
    with pytest.raises(ValueError):
        reg.route("/setup/new", level=Level.ADDRESS)
    with pytest.raises(ValueError):
        reg.route("/elsewhere", level=Level.ADDRESS, setup=SetupStage.OPEN)
    with pytest.raises(ValueError):
        reg.route("/setup/x", level=Level.SECOND_FACTOR, setup=SetupStage.OPEN)
    with pytest.raises(ValueError):
        reg.route("/setup/x", level=Level.ADDRESS, setup=SetupStage.CHECKLIST)
    # a mutating wizard route needs a step-up or a reasoned exemption
    with pytest.raises(ValueError):
        reg.route("/setup/x", level=Level.ADDRESS, methods=["POST"], setup=SetupStage.OPEN)
    reg.route("/setup/x", level=Level.ADDRESS, methods=["POST"], setup=SetupStage.ATTEMPT, stepup_exempt="why")
    reg.route(
        "/setup/y", level=Level.SECOND_FACTOR, methods=["POST"], setup=SetupStage.CHECKLIST,
        stepup=require_stepup(),
    )


async def test_a_setup_session_cannot_reach_any_registered_route_but_enrolment(
    app, runtime_engine
):
    token = await issue(runtime_engine)
    b = Browser(app)
    await redeem(b, token)
    reg = build_registry()
    allowed = {"/mfa", "/mfa/enrol", "/mfa/enrol/confirm", "/logout"}
    for route in reg.router.routes:
        level = route.endpoint.admin_level
        if level < Level.SESSION or route.path in allowed:
            continue
        path = route.path.replace("{session_id}", str(uuid.uuid4())).replace("{key}", "ADMIN_MAIL_SENDER")
        for method in route.methods:
            r = await b.request(method, path)
            # refused: a redirect to sign-in, a 401, or the wizard's bare 404 -- never a page
            assert r.status_code in (303, 401, 403, 404, 405), (method, path, r.status_code)
            if r.status_code == 303:
                assert r.headers["location"] in ("/login", "/mfa", "/mfa/enrol"), (method, path)
    await b.aclose()


async def test_after_a_factor_reset_a_new_token_opens_the_wizard_again(
    app, portal, runtime_engine, clock
):
    b, *_ = await to_enrolled(app, runtime_engine, clock)
    page = await b.get("/setup/mail")
    await b.post("/setup/mail/skip", data={"csrf_token": csrf_from(page)})
    final = await b.get("/setup/finish")
    await b.post("/setup/finish", data={"csrf_token": csrf_from(final), "ack": "yes"})
    assert (await b.get("/setup/mail")).status_code == 404
    # the operator resets the only factor on the host, then asks for a new token
    outcome = await portal.factors.reset_factor(ADMIN, "operator")
    assert outcome.ok
    again, *_ = await to_enrolled(app, runtime_engine, clock)
    state = (await rows(runtime_engine, "SELECT started_by, completed_at, mail_step FROM admin.setup_state"))[0]
    assert tuple(state) == (ADMIN, None, None)
    assert (await again.get("/setup/mail")).status_code == 200
    await b.aclose()
    await again.aclose()


# -- equal answers and equal database work for every refusal ----------------------------


async def test_every_refusal_gives_the_same_answer_and_runs_the_same_statements(
    app, portal, runtime_engine, owner_engine, clock
):
    from tests.admin.test_portal_hardening import Counter

    token = await issue(runtime_engine)
    b = Browser(app)
    form = await b.form_token("/setup")  # taken while the page was open
    seen = {}

    async def attempt(label, token_text, email=ADMIN):
        async with owner_engine.begin() as conn:  # a fresh rate-limit window for each try
            await conn.execute(text("DELETE FROM admin.attempts WHERE key LIKE 'setup_try:%'"))
        with Counter(runtime_engine) as counter:
            r = await b.post(
                "/setup", data={"token": token_text, "email": email, "csrf_token": form}
            )
        seen[label] = (
            (r.status_code, r.headers.get("location"), r.content),
            [st.strip().lower()[:24] for st in counter.statements],
        )

    await attempt("wrong address", token, "stranger@example.org")
    await attempt("wrong token", "AAAA-BBBB-CCCC-DDDD-EEEE-FFFF-GGGG-HHHH")
    async with owner_engine.begin() as conn:
        await conn.execute(text("UPDATE admin.setup_tokens SET expires_at = now() - interval '1 minute'"))
    await attempt("expired", token)
    new = await issue(runtime_engine)
    async with owner_engine.begin() as conn:
        await conn.execute(text("UPDATE admin.setup_tokens SET locked_at = now() WHERE consumed_at IS NULL AND locked_at IS NULL AND revoked_at IS NULL"))
    await attempt("locked", new)
    await enrol_direct(portal, clock, email=OTHER_ADMIN)
    await attempt("setup over", new)

    answers = {label: value[0] for label, value in seen.items()}
    work = {label: value[1] for label, value in seen.items()}
    assert len({repr(a) for a in answers.values()}) == 1, answers
    assert answers["wrong token"] == (303, REFUSED, b"")
    assert len({repr(w) for w in work.values()}) == 1, work


# -- mail form: saved password and TLS defaults -------------------------------------------


async def save_mail(b, transport):
    coded = await start_mail(b)
    code = SIX.search(transport.sent[-1].body).group(1)
    blob = re.search(r'name="pending" value="([^"]+)"', coded.text).group(1)
    ok = await b.post(
        "/setup/mail/confirm",
        data={"csrf_token": csrf_from(coded), "pending": blob, "mail_code": code},
    )
    assert ok.status_code == 303


async def test_a_saved_password_is_never_sent_to_a_different_server(
    app, runtime_engine, clock, transport
):
    b, *_ = await to_enrolled(app, runtime_engine, clock)
    await save_mail(b, transport)
    sent = len(transport.sent)
    for overrides in (
        {"server": "other.example.org"},
        {"port": "2525"},
        {"user": "someone-else"},
    ):
        r = await start_mail(b, password="", **overrides)
        assert r.status_code == 400, overrides
        assert "type the password again" in r.text
        assert MAIL_FORM["password"] not in r.text
    assert len(transport.sent) == sent  # nothing was sent anywhere
    # unchanged server, port and user: a blank password keeps the saved one
    assert (await start_mail(b, password="")).status_code == 200
    # a new password typed for a new server is fine
    assert (await start_mail(b, server="other.example.org", password="another-long-secret-8")).status_code == 200
    await b.aclose()


async def test_never_both_tls_modes_and_the_defaults_are_starttls_587(
    app, runtime_engine, clock, transport
):
    b, *_ = await to_enrolled(app, runtime_engine, clock)
    page = await b.get("/setup/mail")
    assert re.search(r'<select id="m-starttls"[^>]*>\s*<option value="true" selected', page.text)
    assert re.search(r'<select id="m-ssl_tls"[^>]*>\s*<option value="true">[^<]*</option>\s*<option value="false" selected', page.text)
    assert 'placeholder="587"' in page.text
    sent = len(transport.sent)
    both = await start_mail(b, starttls="true", ssl_tls="true")
    assert both.status_code == 400 and "not both" in both.text
    # a client that leaves STARTTLS out inherits its default (on): still refused
    page = await b.get("/setup/mail")
    data = {**MAIL_FORM, "csrf_token": csrf_from(page), "ssl_tls": "true", "port": "465"}
    del data["starttls"]
    r = await b.post("/setup/mail/test", data=data)
    assert r.status_code == 400 and "not both" in r.text
    # implicit TLS alone needs its port stated
    r = await start_mail(b, starttls="false", ssl_tls="true", port="")
    assert r.status_code == 400 and "Enter the port" in r.text
    assert len(transport.sent) == sent
    assert (await start_mail(b, starttls="false", ssl_tls="true", port="465")).status_code == 200
    await b.aclose()
