"""Session lifecycle on real Postgres: expiry, binding, limits, rotation, sweep."""

from __future__ import annotations

import uuid

from sqlalchemy import text

from backend.admin import cookies
from backend.admin.services import sessions as sess
from tests.admin.conftest import needs_postgres
from tests.admin.portal_fixtures import (
    ADMIN,
    OTHER_ADMIN,
    UA,
    Browser,
    make_app,
    sign_in,
)

pytestmark = needs_postgres

IP = "127.0.0.1"


async def rows(engine, sql: str, **params):
    async with engine.connect() as conn:
        return (await conn.execute(text(sql), params)).all()


async def make(portal, email=ADMIN, state="email_ok", ip=IP, ua=UA):
    return await portal.sessions.create(email, ip, ua, mfa_state=state)


async def test_token_is_256_bit_and_only_its_hash_is_stored(portal, runtime_engine):
    token, session = await make(portal)
    assert len(token) >= 43
    stored = (await rows(runtime_engine, "SELECT token_hash FROM admin.sessions"))[0][0]
    assert bytes(stored) == sess.hash_token(token) and token.encode() not in bytes(stored)
    assert (await portal.sessions.authenticate(token, IP, UA)).ok


async def test_unknown_and_garbage_tokens_are_refused(portal):
    for token in (None, "", "x" * 300, "nope"):
        assert (await portal.sessions.authenticate(token, IP, UA)).reason == sess.UNKNOWN


async def test_idle_expiry(portal, clock):
    token, _ = await make(portal)
    clock.advance(29 * 60)
    assert (await portal.sessions.authenticate(token, IP, UA)).ok  # touches
    clock.advance(29 * 60)
    assert (await portal.sessions.authenticate(token, IP, UA)).ok
    clock.advance(31 * 60)
    assert (await portal.sessions.authenticate(token, IP, UA)).reason == sess.IDLE


async def test_absolute_expiry_even_when_active(portal, clock):
    token, _ = await make(portal)
    for _ in range(23):  # 7 h 40 min of activity
        clock.advance(20 * 60)
        assert (await portal.sessions.authenticate(token, IP, UA)).ok
    clock.advance(20 * 60)
    clock.advance(1)
    assert (await portal.sessions.authenticate(token, IP, UA)).reason == sess.ABSOLUTE


async def test_last_seen_moves_at_most_once_a_minute(portal, clock, runtime_engine):
    token, session = await make(portal)
    clock.advance(30)
    await portal.sessions.authenticate(token, IP, UA)
    seen = (await rows(runtime_engine, "SELECT last_seen_at FROM admin.sessions"))[0][0]
    assert seen == session.last_seen_at
    clock.advance(31)
    await portal.sessions.authenticate(token, IP, UA)
    seen = (await rows(runtime_engine, "SELECT last_seen_at FROM admin.sessions"))[0][0]
    assert seen > session.last_seen_at


async def test_revoked_token_is_refused(portal):
    token, session = await make(portal)
    await portal.sessions.logout(session)
    assert (await portal.sessions.authenticate(token, IP, UA)).reason == sess.REVOKED


async def test_binding_mismatch_revokes_and_audits(portal, runtime_engine):
    for ip, ua in (("127.0.0.2", UA), (IP, "other-agent")):
        token, _ = await make(portal)
        assert (await portal.sessions.authenticate(token, ip, ua)).reason == sess.BINDING
        # revoked for good: the original client is refused too
        assert (await portal.sessions.authenticate(token, IP, UA)).reason == sess.REVOKED
    found = await rows(
        runtime_engine,
        "SELECT outcome FROM admin.audit_log WHERE action = 'session.binding_mismatch'",
    )
    assert len(found) == 2


async def test_ipv6_binding_is_per_64(portal):
    token, _ = await make(portal, ip="2001:db8:1:2::1")
    assert (await portal.sessions.authenticate(token, "2001:db8:1:2::ffff", UA)).ok
    assert (await portal.sessions.authenticate(token, "2001:db8:1:3::1", UA)).reason == sess.BINDING


async def test_at_most_three_live_sessions_oldest_revoked(portal, clock, runtime_engine):
    tokens = []
    for _ in range(4):
        tokens.append((await make(portal))[0])
        clock.advance(1)
    live = await portal.sessions.list_live(ADMIN)
    assert len(live) == 3
    assert (await portal.sessions.authenticate(tokens[0], IP, UA)).reason == sess.REVOKED
    assert (await portal.sessions.authenticate(tokens[3], IP, UA)).ok
    reasons = await rows(runtime_engine, "SELECT revoked_reason FROM admin.sessions WHERE revoked_at IS NOT NULL")
    assert [r[0] for r in reasons] == ["session_limit"]
    # another admin's sessions are untouched
    await make(portal, OTHER_ADMIN)
    assert len(await portal.sessions.list_live(ADMIN)) == 3


async def test_promotion_rotates_the_token(portal):
    token, session = await make(portal)
    fresh = await portal.sessions.promote_to_mfa(session, token)
    assert fresh and fresh != token
    assert (await portal.sessions.authenticate(token, IP, UA)).reason == sess.UNKNOWN
    result = await portal.sessions.authenticate(fresh, IP, UA)
    assert result.ok and result.session.mfa_state == "mfa_ok"
    assert portal.sessions.stepup_fresh(result.session)
    assert await portal.sessions.promote_to_mfa(session, token) is None  # replay


async def test_stepup_expires(portal, clock):
    token, session = await make(portal)
    fresh = await portal.sessions.promote_to_mfa(session, token)
    current = (await portal.sessions.authenticate(fresh, IP, UA)).session
    clock.advance(301)
    assert not portal.sessions.stepup_fresh(current)


async def test_revoking_another_admins_session_needs_stepup(portal, clock):
    token, actor = await make(portal, state="mfa_ok")
    _, victim = await make(portal, OTHER_ADMIN, "mfa_ok")
    assert await portal.sessions.revoke_other_admin(actor, victim.id) is None
    token2, s2 = await make(portal)
    fresh = await portal.sessions.promote_to_mfa(s2, token2)
    stepped = (await portal.sessions.authenticate(fresh, IP, UA)).session
    assert await portal.sessions.revoke_other_admin(stepped, victim.id) is True


async def test_revoke_own_and_revoke_all(portal):
    _, a = await make(portal)
    _, b = await make(portal)
    _, other = await make(portal, OTHER_ADMIN)
    assert not await portal.sessions.revoke_own(a, other.id)  # not theirs
    assert await portal.sessions.revoke_own(a, b.id)
    assert await portal.sessions.revoke_all(ADMIN, keep=a.id) == 0
    assert await portal.sessions.revoke_all(ADMIN) == 1


async def test_startup_sweep_revokes_removed_admins(portal, make_portal):
    token, _ = await make(portal, OTHER_ADMIN)
    kept, _ = await make(portal, ADMIN)
    narrower = make_portal(admins=(ADMIN,))
    assert await narrower.startup() == 1
    assert (await portal.sessions.authenticate(token, IP, UA)).reason == sess.REVOKED
    assert (await portal.sessions.authenticate(kept, IP, UA)).ok


async def test_level_three_revokes_when_email_leaves_the_list(
    portal, make_portal, runtime_engine, transport
):
    b = Browser(make_app(portal))
    await sign_in(b, transport, ADMIN)
    stricter = Browser(make_app(make_portal(admins=(OTHER_ADMIN,))))
    stricter.cookies = dict(b.cookies)
    r = await stricter.get("/mfa")
    assert r.status_code == 303 and r.headers["location"] == "/login"
    revoked = await rows(runtime_engine, "SELECT revoked_reason FROM admin.sessions")
    assert revoked[0][0] == "admin_removed"
    await b.aclose()
    await stricter.aclose()


async def test_logout_revokes_clears_cookie_and_audits(app, transport, runtime_engine):
    b = Browser(app)
    token = await sign_in(b, transport)
    page = await b.get("/mfa/enrol")
    assert page.status_code == 200 and "Set up an authenticator" in page.text
    csrf = page.text.split('name="csrf_token" value="')[1].split('"')[0]
    r = await b.post("/logout", data={"csrf_token": csrf})
    assert r.status_code == 303 and r.headers["location"] == "/login"
    assert cookies.SESSION_COOKIE not in b.cookies
    other = Browser(app)
    other.cookies[cookies.SESSION_COOKIE] = token
    assert (await other.get("/mfa")).headers["location"] == "/login"
    got = await rows(runtime_engine, "SELECT action FROM admin.audit_log WHERE action = 'session.logout'")
    assert len(got) == 1
    await b.aclose()
    await other.aclose()


async def test_session_cookie_attributes(app, transport):
    b = Browser(app)
    await sign_in(b, transport)
    line = next(l for l in b.set_cookie_lines if l.startswith("__Host-bcadmin="))
    low = line.lower()
    assert "secure" in low and "httponly" in low and "samesite=strict" in low
    assert "path=/" in low and "domain" not in low and "expires" not in low
    await b.aclose()


async def test_cleanup_removes_old_rows(portal, clock):
    _, session = await make(portal)
    await portal.sessions.logout(session)
    clock.advance(8 * 86400)
    assert (await portal.sessions.cleanup())["sessions"] == 1


async def test_session_ids_are_uuids(portal):
    _, session = await make(portal)
    assert isinstance(session.id, uuid.UUID)


async def test_operator_revoke_everyone_is_audited_as_cli(portal, runtime_engine):
    token, _ = await make(portal)
    await make(portal, OTHER_ADMIN)
    assert await portal.sessions.revoke_everyone() == 2
    assert (await portal.sessions.authenticate(token, IP, UA)).reason == sess.REVOKED
    found = await rows(
        runtime_engine,
        "SELECT actor_kind, detail->>'reason' FROM admin.audit_log WHERE action = 'session.revoked'",
    )
    assert {tuple(r) for r in found} == {("cli", "cli_revoke")}
