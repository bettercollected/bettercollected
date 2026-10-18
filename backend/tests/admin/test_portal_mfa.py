"""Second factor, recovery codes and step-up on real Postgres."""

from __future__ import annotations

import asyncio
import base64
import re
import uuid

import pytest
from fastapi import Request
from sqlalchemy import text

from backend.admin import cookies
from backend.admin.__main__ import main as cli_main
from backend.admin.asgi import get_admin_application
from backend.admin.controllers.portal import build_registry
from backend.admin.gate import stepup as step
from backend.admin.gate.levels import Level, RouteRegistry
from backend.admin.gate.settings import GateSettings
from backend.admin.security import csrf, envelope, totp
from backend.admin.security.keys import admin_key
from backend.admin.services import factors as fsvc
from backend.admin.services.stepup import TOKEN_SECONDS, action_hash
from tests.admin.conftest import MASTER_KEY, needs_postgres
from tests.admin.portal_fixtures import (
    ADMIN,
    OTHER_ADMIN,
    TOKEN_RE,
    UA,
    Browser,
    sign_in,
)

pytestmark = needs_postgres

IP = "127.0.0.1"
SECRET_RE = re.compile(r'<code class="secret">([A-Z2-7 ]+)</code>')
CODES_RE = re.compile(r"<li><code>([A-Z2-7-]+)</code></li>")
FACTOR_RE = re.compile(r'name="factor_id" value="([^"]+)"')


async def rows(engine, sql: str, **params):
    async with engine.connect() as conn:
        return (await conn.execute(text(sql), params)).all()


async def actions(engine):
    return [r[0] for r in await rows(engine, "SELECT action FROM admin.audit_log ORDER BY seq")]


async def run_after(outcome):
    for job in outcome.after:
        await job()


async def new_session(portal, email=ADMIN, ip=IP, state="email_ok"):
    return await portal.sessions.create(email, ip, UA, mfa_state=state)


async def enrol_direct(portal, clock, email=ADMIN, ip=IP):
    """Enrol through the service; returns (secret, codes, session_token, session)."""
    token, session = await new_session(portal, email, ip)
    start = await portal.factors.start_enrol(session, ip, UA, None)
    secret = start.secret.replace(" ", "")
    done = await portal.factors.confirm_enrol(
        session, token, start.factor_id, totp.code_at(secret, clock.time()), ip, UA, None
    )
    assert done.ok
    return secret, done.codes, done.new_token, await portal.sessions.reload(session)


async def signed_in_unverified(portal, email=ADMIN, ip=IP):
    return await new_session(portal, email, ip)


def csrf_of(portal, session) -> str:
    return csrf.session_token(portal.csrf_key, session.csrf_subject)


async def enrol_browser(b, transport, clock):
    await sign_in(b, transport)
    page = await b.get("/mfa/enrol")
    token = TOKEN_RE.search(page.text).group(1)
    started = await b.post("/mfa/enrol", data={"csrf_token": token})
    secret = SECRET_RE.search(started.text).group(1).replace(" ", "")
    factor_id = FACTOR_RE.search(started.text).group(1)
    return token, secret, factor_id, started


# -- enrolment ------------------------------------------------------------------


async def test_enrol_flow_end_to_end(app, portal, transport, clock, runtime_engine):
    b = Browser(app)
    token, secret, factor_id, started = await enrol_browser(b, transport, clock)
    # the QR is an inline SVG data URI drawn locally, with nothing active in it
    uri = re.search(r'src="(data:image/svg\+xml;base64,[^"]+)"', started.text).group(1)
    svg = base64.b64decode(uri.split(",", 1)[1]).decode()
    assert svg.startswith("<svg") and not re.search(r"<script|href=|https?://(?!www\.w3\.org)", svg)
    assert "no-store" in started.headers["cache-control"]
    assert "img-src 'self' data:" in started.headers["content-security-policy"]

    # the secret is stored sealed, bound to factor id and email
    blob, = (await rows(runtime_engine, "SELECT secret_blob FROM admin.factors"))[0]
    assert secret not in blob and blob.startswith("v1:")
    key = admin_key("totp", env={"SETTINGS_MASTER_KEY": MASTER_KEY})
    assert envelope.decrypt(blob, key, f"{factor_id}|{ADMIN}".encode()) == secret.encode()
    with pytest.raises(envelope.EnvelopeError):
        envelope.decrypt(blob, key, f"{uuid.uuid4()}|{ADMIN}".encode())

    # a wrong code does not confirm
    wrong = await b.post(
        "/mfa/enrol/confirm", data={"csrf_token": token, "factor_id": factor_id, "code": "000000"}
    )
    assert wrong.status_code == 200 and "did not work" in wrong.text
    assert (await rows(runtime_engine, "SELECT confirmed_at FROM admin.factors"))[0][0] is None
    assert (await b.get("/")).status_code == 303

    # the right one confirms, shows ten codes once, rotates the session
    old_cookie = b.cookies[cookies.SESSION_COOKIE]
    ok = await b.post(
        "/mfa/enrol/confirm",
        data={"csrf_token": token, "factor_id": factor_id, "code": totp.code_at(secret, clock.time())},
    )
    assert ok.status_code == 200 and "no-store" in ok.headers["cache-control"]
    codes = CODES_RE.findall(ok.text)
    assert len(codes) == 10 and len(set(codes)) == 10
    assert b.cookies[cookies.SESSION_COOKIE] != old_cookie
    stale = Browser(app)
    stale.cookies[cookies.SESSION_COOKIE] = old_cookie
    assert (await stale.get("/")).status_code == 303 and (await stale.get("/api/me")).status_code == 401
    assert (await b.get("/")).status_code == 200
    assert (await b.get("/api/me")).json()["mfa_state"] == "mfa_ok"

    # stored hashed, never shown again
    stored = await rows(runtime_engine, "SELECT code_hash FROM admin.recovery_codes")
    assert len(stored) == 10
    assert all(len(bytes(r[0])) == 32 for r in stored)
    again = await b.get("/mfa/recovery-codes")
    assert again.status_code == 200 and not CODES_RE.findall(again.text)

    # everyone is told; audited in the same transaction as the change
    assert sorted(transport.recipients[-2:]) == sorted([ADMIN, OTHER_ADMIN])
    assert "second factor was set up" in transport.sent[-1].subject.lower() or "second factor" in transport.sent[-1].subject
    log = await actions(runtime_engine)
    assert "mfa.enrol_started" in log and "mfa.enrolled" in log and "session.rotated" in log
    await b.aclose()
    await stale.aclose()


async def test_email_ok_session_state_narrows_the_mfa_pages(app, portal, transport, clock):
    b = Browser(app)
    await sign_in(b, transport)
    # no factor yet: /mfa -> enrol, verify is not available
    assert (await b.get("/mfa")).headers["location"] == "/mfa/enrol"
    assert (await b.get("/mfa/verify")).headers["location"] == "/mfa/enrol"
    assert (await b.get("/mfa/enrol")).status_code == 200
    await b.aclose()
    # with a confirmed factor: verify only
    await enrol_direct(portal, clock)
    c = Browser(app)
    await sign_in(c, transport)
    assert (await c.get("/mfa")).headers["location"] == "/mfa/verify"
    assert (await c.get("/mfa/enrol")).headers["location"] == "/mfa/verify"
    assert (await c.get("/mfa/verify")).status_code == 200
    token = TOKEN_RE.search((await c.get("/mfa/verify")).text).group(1)
    r = await c.post("/mfa/enrol", data={"csrf_token": token})
    assert r.status_code == 303 and r.headers["location"] == "/mfa/verify"
    await c.aclose()


def _paths(level_ok):
    reg = build_registry()
    out = []
    for route in reg.router.routes:
        level = route.endpoint.admin_level
        if "GET" in route.methods and level_ok(level):
            out.append(route.path)
    return out


@pytest.mark.parametrize("path", _paths(lambda lv: lv >= Level.SESSION))
@pytest.mark.parametrize("has_factor", [False, True])
async def test_gate_for_email_ok_sessions_over_the_registry(
    path, has_factor, app, portal, transport, clock
):
    if has_factor:
        await enrol_direct(portal, clock)
    b = Browser(app)
    await sign_in(b, transport)
    response = await b.get(path.replace("{session_id}", str(uuid.uuid4())))
    allowed = "/mfa/verify" if has_factor else "/mfa/enrol"
    if path == allowed:
        assert response.status_code == 200
    elif path.startswith("/setup"):
        assert response.status_code == 404 and response.content == b"", path  # the wizard's bare 404
    else:
        assert response.status_code in (303, 401), path
        if response.status_code == 303:
            assert response.headers["location"].startswith("/mfa") or path.startswith("/mfa")
    await b.aclose()


# -- verification ---------------------------------------------------------------


async def test_verify_login_rotates_token_and_rejects_replay(portal, clock, runtime_engine):
    secret, _, _, _ = await enrol_direct(portal, clock)
    clock.advance(30)
    code = totp.code_at(secret, clock.time())
    token, session = await new_session(portal)
    out = await portal.factors.verify_login(session, token, code, IP, UA, None)
    assert out.ok and out.new_token and out.new_token != token and out.method == "totp"
    # the same code (same step) never works twice
    token2, session2 = await new_session(portal)
    again = await portal.factors.verify_login(session2, token2, code, IP, UA, None)
    assert not again.ok and again.reason == fsvc.WRONG
    assert "mfa.verified" in await actions(runtime_engine)


async def test_two_concurrent_verifies_of_one_code_exactly_one_wins(portal, clock):
    secret, _, _, _ = await enrol_direct(portal, clock)
    clock.advance(30)
    code = totp.code_at(secret, clock.time())
    pairs = [await new_session(portal) for _ in range(2)]
    results = await asyncio.gather(
        *(portal.factors.verify_login(s, t, code, IP, UA, None) for t, s in pairs)
    )
    assert sorted(r.ok for r in results) == [False, True]


@pytest.mark.parametrize("offset,accepted", [(-60, False), (-30, True), (0, True), (30, True), (60, False)])
async def test_drift_boundaries(offset, accepted, portal, clock, runtime_engine):
    secret, _, _, _ = await enrol_direct(portal, clock)
    clock.advance(300)  # well past the enrolment step
    async with portal.engine.begin() as conn:
        await conn.execute(text("UPDATE admin.factors SET last_used_step = NULL"))
    token, session = await new_session(portal)
    code = totp.code_at(secret, clock.time() + offset)
    out = await portal.factors.verify_login(session, token, code, IP, UA, None)
    assert out.ok is accepted


async def test_recovery_code_is_single_use_mails_everyone_and_is_audited(
    portal, clock, transport, runtime_engine
):
    _, codes, _, _ = await enrol_direct(portal, clock)
    transport.sent.clear()
    transport.recipients.clear()
    token, session = await new_session(portal)
    out = await portal.factors.verify_login(session, token, codes[0].lower(), IP, UA, None)
    assert out.ok and out.method == "recovery"
    await run_after(out)
    assert sorted(transport.recipients) == sorted([ADMIN, OTHER_ADMIN])
    assert "recovery code" in transport.sent[0].subject
    assert "Recovery codes left: 9" in transport.sent[0].body
    token2, session2 = await new_session(portal)
    reuse = await portal.factors.verify_login(session2, token2, codes[0], IP, UA, None)
    assert not reuse.ok
    assert "mfa.recovery_used" in await actions(runtime_engine)
    # the mail never carries a code
    assert codes[0] not in transport.sent[0].body


async def test_lockout_escalation_and_mail(portal, clock, transport, runtime_engine):
    secret, _, _, _ = await enrol_direct(portal, clock)
    transport.sent.clear()
    transport.recipients.clear()
    token, session = await new_session(portal)
    outcomes = []
    for _ in range(5):
        outcomes.append(await portal.factors.verify_login(session, token, "000000", IP, UA, None))
    assert [o.reason for o in outcomes] == [fsvc.WRONG] * 5
    await run_after(outcomes[-1])
    assert sorted(transport.recipients) == sorted([ADMIN, OTHER_ADMIN])
    assert "locked" in transport.sent[0].subject
    clock.advance(30)
    right = await portal.factors.verify_login(
        session, token, totp.code_at(secret, clock.time()), IP, UA, None
    )
    assert not right.ok and right.reason == fsvc.LOCKED and right.retry_minutes >= 1
    clock.advance(15 * 60 + 60)
    clock.advance(30)
    ok = await portal.factors.verify_login(
        session, token, totp.code_at(secret, clock.time()), IP, UA, None
    )
    assert ok.ok
    assert "signin.locked" in await actions(runtime_engine)


async def test_slow_guessing_locks_by_the_rolling_24h_rule(portal, clock):
    await enrol_direct(portal, clock)
    token, session = await new_session(portal)
    for attempt in range(1, 16):
        out = await portal.factors.verify_login(session, token, "000000", IP, UA, None)
        assert out.reason == fsvc.WRONG
        if attempt < 15:
            assert not (await portal.limiter.lock_status(ADMIN)).locked
        clock.advance(301)  # each failure in its own five-minute window
    assert (await portal.limiter.lock_status(ADMIN)).locked


async def test_unseen_address_mails_all_admins(portal, clock, transport):
    secret, _, _, _ = await enrol_direct(portal, clock, ip="10.1.1.1")
    clock.advance(30)
    transport.sent.clear()
    token, session = await new_session(portal, ip="10.9.9.9")
    out = await portal.factors.verify_login(
        session, token, totp.code_at(secret, clock.time()), "10.9.9.9", UA, None
    )
    assert out.ok
    await run_after(out)
    assert any("new address" in m.subject for m in transport.sent)
    transport.sent.clear()
    clock.advance(30)
    token, session = await new_session(portal, ip="10.9.9.9")
    again = await portal.factors.verify_login(
        session, token, totp.code_at(secret, clock.time()), "10.9.9.9", UA, None
    )
    assert again.ok and not again.after  # the address is known now


# -- step-up --------------------------------------------------------------------


async def mfa_session(portal, clock):
    secret, codes, token, session = await enrol_direct(portal, clock)
    return secret, codes, token, session


async def test_stepup_window_edges(portal, clock):
    _, _, _, session = await mfa_session(portal, clock)
    assert portal.sessions.stepup_fresh(session)
    clock.advance(299)
    assert portal.sessions.stepup_fresh(session)
    clock.advance(2)  # 301 s
    assert not portal.sessions.stepup_fresh(session)


async def test_stepup_seconds_setting_is_bounded():
    from backend.admin.portal_config import PortalConfigError, PortalSettings

    assert PortalSettings.from_env({}).stepup_seconds == 300
    assert PortalSettings.from_env({"ADMIN_STEPUP_SECONDS": "600"}).stepup_seconds == 600
    for bad in ("601", "0", "x", "-5"):
        with pytest.raises(PortalConfigError):
            PortalSettings.from_env({"ADMIN_STEPUP_SECONDS": bad})


async def test_revoke_other_admin_needs_a_fresh_stepup(portal, clock):
    secret, _, _, session = await mfa_session(portal, clock)
    _, other = await new_session(portal, OTHER_ADMIN)
    clock.advance(400)
    session = await portal.sessions.reload(session)
    assert await portal.sessions.revoke_other_admin(session, other.id) is None
    out = await portal.factors.verify_stepup(
        session, totp.code_at(secret, clock.time()), IP, UA, None
    )
    assert out.ok and out.method == "totp"
    session = await portal.sessions.reload(session)
    assert await portal.sessions.revoke_other_admin(session, other.id) is True


async def test_stepup_by_totp_or_recovery_code_and_regeneration(portal, clock, runtime_engine):
    secret, codes, _, session = await mfa_session(portal, clock)
    clock.advance(400)
    session = await portal.sessions.reload(session)
    assert (await portal.factors.regenerate_codes(session, IP, UA, None)).reason == fsvc.STEPUP_REQUIRED
    # a recovery code counts as a factor for step-up
    out = await portal.factors.verify_stepup(session, codes[0], IP, UA, None)
    assert out.ok and out.method == "recovery"
    session = await portal.sessions.reload(session)
    assert portal.sessions.stepup_fresh(session)
    _, other = await new_session(portal, OTHER_ADMIN)
    assert await portal.sessions.revoke_other_admin(session, other.id) is True
    new = await portal.factors.regenerate_codes(session, IP, UA, None)
    assert new.ok and len(new.codes) == 10 and not set(new.codes) & set(codes)
    # the old set is dead, the new one works
    token, s2 = await new_session(portal)
    assert not (await portal.factors.verify_login(s2, token, codes[1], IP, UA, None)).ok
    token, s3 = await new_session(portal)
    assert (await portal.factors.verify_login(s3, token, new.codes[0], IP, UA, None)).ok
    left = (await rows(runtime_engine, "SELECT count(*) FROM admin.recovery_codes WHERE used_at IS NULL"))[0][0]
    assert left == 9
    assert "mfa.recovery_regenerated" in await actions(runtime_engine)


async def test_stepup_pages_through_the_browser(app, portal, transport, clock, runtime_engine):
    b = Browser(app)
    token, secret, factor_id, _ = await enrol_browser(b, transport, clock)
    await b.post(
        "/mfa/enrol/confirm",
        data={"csrf_token": token, "factor_id": factor_id, "code": totp.code_at(secret, clock.time())},
    )
    clock.advance(301)
    page = await b.get("/mfa/recovery-codes")
    t = TOKEN_RE.search(page.text).group(1)
    refused = await b.post("/mfa/recovery-codes", data={"csrf_token": t})
    assert refused.status_code == 303 and refused.headers["location"] == "/mfa/stepup?next=/mfa/recovery-codes"
    prompt = await b.get(refused.headers["location"])
    assert 'autocomplete="one-time-code"' in prompt.text
    bad_next = await b.post(
        "/mfa/stepup",
        data={"csrf_token": t, "next": "https://evil.example/", "code": totp.code_at(secret, clock.time())},
    )
    assert bad_next.status_code == 303 and bad_next.headers["location"] == "/account"  # never an open redirect
    again = await b.post("/mfa/recovery-codes", data={"csrf_token": t})
    assert again.status_code == 200 and len(CODES_RE.findall(again.text)) == 10
    await b.aclose()


async def test_adding_or_replacing_a_factor_needs_stepup(app, portal, transport, clock):
    _, _, token, session = await mfa_session(portal, clock)
    clock.advance(400)
    session = await portal.sessions.reload(session)
    out = await portal.factors.start_enrol(session, IP, UA, None)
    assert isinstance(out, fsvc.Outcome) and out.reason == fsvc.STEPUP_REQUIRED


# -- action-bound tokens and the route attribute -------------------------------------


def _bound_app(portal):
    reg = build_registry()
    seen = []

    async def parts(request: Request):
        return [(await request.json())["target"]]

    @reg.route(
        "/api/danger", level=Level.SECOND_FACTOR, methods=["POST"],
        stepup=step.ActionBound("danger", parts),
    )
    async def danger(request: Request):
        seen.append(1)
        return {"done": True}

    return get_admin_application(GateSettings.from_env({}), portal=portal, router_registry=reg), seen


async def test_action_bound_token_rules(portal, clock, runtime_engine):
    app, seen = _bound_app(portal)
    secret, codes, token, session = await mfa_session(portal, clock)
    b = Browser(app)
    b.cookies[cookies.SESSION_COOKIE] = token
    h = {"x-csrf-token": csrf_of(portal, session)}

    async def call(target, tok=None):
        headers = dict(h)
        if tok:
            headers["x-stepup-token"] = tok
        return await b.post("/api/danger", json={"target": target}, headers=headers)

    assert (await call("a")).status_code == 403  # no token
    tok = portal.stepup.issue(session, action_hash("danger", "a"))
    assert tok
    assert (await call("b", tok)).status_code == 403  # bound to another value
    assert (await call("a", tok)).status_code == 200 and seen == [1]
    assert (await call("a", tok)).status_code == 403  # single use
    tok2 = portal.stepup.issue(session, action_hash("danger", "a"))
    clock.advance(TOKEN_SECONDS + 1)
    assert (await call("a", tok2)).status_code == 403  # expired
    # another session cannot use it, and it is only issued while fresh
    _, other = await new_session(portal, OTHER_ADMIN, state="mfa_ok")
    clock.advance(0)
    assert not await portal.stepup.consume(other, tok2, action_hash("danger", "a"))
    assert portal.stepup.issue(session, action_hash("danger", "a")) is None  # window long past
    assert not await portal.stepup.consume(session, "garbage", action_hash("danger", "a"))
    await b.aclose()


async def test_api_stepup_issues_a_token_for_a_registered_action(portal, clock):
    app, seen = _bound_app(portal)
    secret, codes, token, session = await mfa_session(portal, clock)
    clock.advance(400)
    b = Browser(app)
    b.cookies[cookies.SESSION_COOKIE] = token
    h = {"x-csrf-token": csrf_of(portal, session)}
    bad = await b.post("/api/stepup", json={"code": "1", "action": "nope"}, headers=h)
    assert bad.status_code == 400
    wrong = await b.post("/api/stepup", json={"code": "000000", "action": "danger", "parts": ["a"]}, headers=h)
    assert wrong.status_code == 403
    got = await b.post(
        "/api/stepup", json={"code": codes[0], "action": "danger", "parts": ["a"]}, headers=h
    )
    assert got.status_code == 200 and got.json()["expires_in"] == TOKEN_SECONDS
    done = await b.post(
        "/api/danger", json={"target": "a"}, headers={**h, "x-stepup-token": got.json()["token"]}
    )
    assert done.status_code == 200 and seen == [1]
    await b.aclose()


def test_every_declared_stepup_is_enforced_and_declarations_are_checked():
    reg = build_registry()
    declared = [r for r in reg.router.routes if getattr(r.endpoint, step.STEPUP_ATTR, None)]
    assert declared  # at least regenerate-recovery-codes
    for route in declared:
        assert route.dependencies, route.path  # enforced by a dependency, not by the handler
    # settings and tasks pages (later PRs) must declare one on every mutating route
    assert step.undeclared_mutating_routes(reg.router.routes, ("/settings", "/tasks")) == []
    fake = RouteRegistry()
    # default deny: a mutating route under /settings or /tasks must say how it is protected
    for path in ("/settings/x", "/tasks/run"):
        with pytest.raises(ValueError):
            fake.route(path, level=Level.SECOND_FACTOR, methods=["POST"])
    with pytest.raises(ValueError):
        fake.route("/settings/x", level=Level.SECOND_FACTOR, methods=["POST"], stepup_exempt=" ")

    @fake.route("/settings/view", level=Level.SECOND_FACTOR)  # reading is free
    async def view():
        return {}

    @fake.route("/settings/ok", level=Level.SECOND_FACTOR, methods=["POST"], stepup_exempt="echoes a preview only")
    async def ok():
        return {}

    @fake.route("/tasks/run", level=Level.SECOND_FACTOR, methods=["POST"], stepup=step.StepUp())
    async def run():
        return {}

    assert step.undeclared_mutating_routes(fake.router.routes, ("/settings", "/tasks")) == []
    with pytest.raises(ValueError):
        fake.route("/settings/y", level=Level.SECOND_FACTOR, stepup=step.ActionBound("y"))  # GET
    with pytest.raises(ValueError):
        fake.route("/settings/z", level=Level.ADMIN, methods=["POST"], stepup=step.StepUp())


# -- CSRF, headers, templates -------------------------------------------------------


MFA_POSTS = [
    "/mfa/enrol", "/mfa/enrol/confirm", "/mfa/verify", "/mfa/stepup", "/mfa/recovery-codes",
    "/mfa/recovery-codes/saved", "/account/sessions/revoke-others",
    "/account/sessions/00000000-0000-4000-8000-000000000001/revoke", "/logout",
]


@pytest.mark.parametrize("path", MFA_POSTS)
async def test_new_posts_need_the_csrf_token(path, app, portal, clock):
    _, _, token, session = await mfa_session(portal, clock)
    b = Browser(app)
    b.cookies[cookies.SESSION_COOKIE] = token
    r = await b.post(path, data={"code": "000000"})
    assert r.status_code == 403
    r = await b.post(path, data={"code": "000000", "csrf_token": "x" * 40})
    assert r.status_code == 403
    await b.aclose()


async def test_account_page_lists_sessions_and_pages_carry_csp(app, portal, clock):
    _, _, token, session = await mfa_session(portal, clock)
    b = Browser(app)
    b.cookies[cookies.SESSION_COOKIE] = token
    r = await b.get("/account")
    assert r.status_code == 200 and "this session" in r.text
    assert "default-src 'none'" in r.headers["content-security-policy"]
    t = TOKEN_RE.search(r.text).group(1)
    assert (await b.post("/account/sessions/revoke-others", data={"csrf_token": t})).status_code == 303
    await b.aclose()


# -- break glass --------------------------------------------------------------------------


async def test_reset_factor_removes_everything_and_forces_reenrolment(
    portal, clock, transport, runtime_engine
):
    _, _, token, session = await mfa_session(portal, clock)
    transport.sent.clear()
    out = await portal.factors.reset_factor(ADMIN, "operator")
    await run_after(out)
    assert (await rows(runtime_engine, "SELECT count(*) FROM admin.factors"))[0][0] == 0
    assert (await rows(runtime_engine, "SELECT count(*) FROM admin.recovery_codes"))[0][0] == 0
    assert await portal.sessions.reload(session) is None  # revoked
    assert sorted(transport.recipients[-2:]) == sorted([ADMIN, OTHER_ADMIN])
    entry = (
        await rows(
            runtime_engine,
            "SELECT actor_kind, detail->>'os_user' FROM admin.audit_log WHERE action = 'cli.reset_factor'",
        )
    )[0]
    assert tuple(entry) == ("cli", "operator")
    status = await portal.factors.status(ADMIN)
    assert not status.confirmed  # the next email sign-in lands on /mfa/enrol


def test_cli_reset_factor_refuses_without_yes_or_for_unlisted_email(monkeypatch, capsys):
    monkeypatch.setenv("PLATFORM_ADMIN_EMAILS", ADMIN)
    assert cli_main(["reset-factor", "--email", ADMIN]) == 2
    assert cli_main(["reset-factor", "--email", "stranger@example.net", "--yes"]) == 2
    err = capsys.readouterr().err
    assert "--yes" in err and "PLATFORM_ADMIN_EMAILS" in err


# -- limiter: guesses are reserved before they are evaluated ---------------------------------


async def test_parallel_wrong_codes_are_not_all_evaluated(portal, clock, monkeypatch):
    await enrol_direct(portal, clock)
    pairs = [await new_session(portal) for _ in range(20)]
    evaluated = []
    original = fsvc.FactorService._match

    async def counting(self, *args, **kwargs):
        evaluated.append(1)
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(fsvc.FactorService, "_match", counting)
    results = await asyncio.gather(
        *(portal.factors.verify_login(s, t, "000000", IP, UA, None) for t, s in pairs)
    )
    assert len(evaluated) <= 5
    assert sum(1 for r in results if r.reason == fsvc.WRONG) == len(evaluated)
    assert sum(1 for r in results if r.reason == fsvc.LOCKED) == 20 - len(evaluated)
    assert (await portal.limiter.lock_status(ADMIN)).locked


async def test_parallel_wrong_codes_at_enrolment_are_limited_too(portal, clock, monkeypatch):
    token, session = await new_session(portal)
    start = await portal.factors.start_enrol(session, IP, UA, None)
    calls = []
    original = fsvc.totp.verify

    def counting(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(fsvc.totp, "verify", counting)
    results = await asyncio.gather(
        *(portal.factors.confirm_enrol(session, token, start.factor_id, "000000", IP, UA, None) for _ in range(20))
    )
    assert len(calls) <= 5 and not any(r.ok for r in results)


async def test_correct_code_after_four_wrong_ones_works_and_resets(portal, clock):
    secret, _, _, _ = await enrol_direct(portal, clock)
    clock.advance(30)
    token, session = await new_session(portal)
    for _ in range(4):
        assert (await portal.factors.verify_login(session, token, "000000", IP, UA, None)).reason == fsvc.WRONG
    ok = await portal.factors.verify_login(
        session, token, totp.code_at(secret, clock.time()), IP, UA, None
    )
    assert ok.ok
    # the reservations and the failure counter were reset: four more wrong guesses
    # are evaluated again (and the account is not locked)
    token2, s2 = await new_session(portal)
    for _ in range(4):
        assert (await portal.factors.verify_login(s2, token2, "000000", IP, UA, None)).reason == fsvc.WRONG
    assert not (await portal.limiter.lock_status(ADMIN)).locked


async def test_a_recovery_code_after_wrong_guesses_also_works(portal, clock):
    _, codes, _, _ = await enrol_direct(portal, clock)
    token, session = await new_session(portal)
    for _ in range(4):
        await portal.factors.verify_login(session, token, "AAAA-AAAA-AAAA-AAAA", IP, UA, None)
    assert (await portal.factors.verify_login(session, token, codes[0], IP, UA, None)).ok


async def test_step_up_guesses_share_the_same_reservation(portal, clock, monkeypatch):
    _, _, _, session = await mfa_session(portal, clock)
    evaluated = []
    original = fsvc.FactorService._match

    async def counting(self, *a, **k):
        evaluated.append(1)
        return await original(self, *a, **k)

    monkeypatch.setattr(fsvc.FactorService, "_match", counting)
    await asyncio.gather(*(portal.factors.verify_stepup(session, "000000", IP, UA, None) for _ in range(20)))
    assert len(evaluated) <= 5


# -- unseen address: only verified sessions count -----------------------------------------------


async def test_an_address_seen_only_in_an_unverified_session_is_still_new(portal, clock, transport):
    secret, _, _, _ = await enrol_direct(portal, clock, ip="10.1.1.1")
    await new_session(portal, ip="10.5.5.5")  # email step only, never passed the factor
    clock.advance(30)
    transport.sent.clear()
    token, session = await new_session(portal, ip="10.5.5.5")
    out = await portal.factors.verify_login(
        session, token, totp.code_at(secret, clock.time()), "10.5.5.5", UA, None
    )
    assert out.ok
    await run_after(out)
    assert any("new address" in m.subject for m in transport.sent)


# -- two factors confirmed at once ----------------------------------------------------------------


async def test_two_concurrent_confirmations_leave_exactly_one_factor(portal, clock, runtime_engine):
    from backend.admin.repositories import factors as repo

    pairs = [await new_session(portal) for _ in range(2)]
    first = await portal.factors.start_enrol(pairs[0][1], IP, UA, None)
    # a second pending factor, as a race between two starts would leave
    second_id, second_secret = uuid.uuid4(), totp.generate_secret()
    async with portal.engine.begin() as conn:
        await repo.insert_factor(
            conn, second_id, ADMIN,
            portal.factors._seal(second_secret, second_id, ADMIN), "totp1", portal.clock.now(),
        )
    secrets_ = [first.secret.replace(" ", ""), second_secret]
    ids = [first.factor_id, second_id]
    results = await asyncio.gather(
        *(
            portal.factors.confirm_enrol(
                pairs[i][1], pairs[i][0], ids[i], totp.code_at(secrets_[i], clock.time()), IP, UA, None
            )
            for i in range(2)
        )
    )
    assert sorted(r.ok for r in results) == [False, True]
    confirmed = await rows(runtime_engine, "SELECT count(*) FROM admin.factors WHERE confirmed_at IS NOT NULL")
    assert confirmed[0][0] == 1
    assert (await rows(runtime_engine, "SELECT count(*) FROM admin.recovery_codes"))[0][0] == 10
