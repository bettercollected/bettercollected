"""Sign-in hardening: equal database work for admin and non-admin paths, bounded
growth under flooding, the session cap under concurrency, CSRF across rotation."""

from __future__ import annotations

import asyncio

from sqlalchemy import event, text

from backend.admin import cookies
from backend.admin.security import csrf
from tests.admin.conftest import needs_postgres
from tests.admin.portal_fixtures import ADMIN, UA, Browser, last_code

pytestmark = needs_postgres

NON_ADMIN = "stranger@example.net"
IP = "127.0.0.1"


class Counter:
    """Counts the SQL statements an engine executes while it is active."""

    def __init__(self, engine) -> None:
        self.sync = engine.sync_engine
        self.statements: list = []

    def _hook(self, conn, cursor, statement, *rest):
        self.statements.append(statement)

    def __enter__(self):
        event.listen(self.sync, "before_cursor_execute", self._hook)
        return self

    def __exit__(self, *exc):
        event.remove(self.sync, "before_cursor_execute", self._hook)

    @property
    def count(self) -> int:
        return len(self.statements)


async def rows(engine, sql: str, **params):
    async with engine.connect() as conn:
        return (await conn.execute(text(sql), params)).all()


# -- 1. equal database work ---------------------------------------------------


async def test_login_runs_the_same_statements_for_admin_and_non_admin(
    app, runtime_engine
):
    counts = {}
    for label, email in (
        ("non_admin", NON_ADMIN),
        ("admin", ADMIN),  # issues a challenge
        ("admin_again", ADMIN),
        ("admin_third", ADMIN),
        ("admin_limited", ADMIN),  # 4th in the window: rate limited, nothing issued
        ("non_admin_limited", "other@example.net"),
    ):
        b = Browser(app)
        with Counter(runtime_engine) as c:
            await b.request_code(email)
        counts[label] = c.count - 0
        await b.aclose()
    # each request_code() helper also GETs /login first (no database): compare as is
    assert len(set(counts.values())) == 1, counts


async def test_wrong_codes_run_the_same_statements_for_admin_and_non_admin_challenges(
    app, runtime_engine, transport
):
    admin, stranger = Browser(app), Browser(app)
    await admin.request_code(ADMIN)
    await stranger.request_code(NON_ADMIN)
    wrong = "00000000" if last_code(transport) != "00000000" else "11111111"
    seen = []
    for attempt in range(1, 8):  # past the 5-attempt cap and the lockout
        pair = []
        for b in (admin, stranger):
            token = await b.form_token("/login/code")
            with Counter(runtime_engine) as c:
                r = await b.post("/login/code", data={"code": wrong, "csrf_token": token})
            assert r.status_code == 200
            pair.append(c.count)
        seen.append(pair)
        assert pair[0] == pair[1], (attempt, seen)
    await admin.aclose()
    await stranger.aclose()


async def test_non_admin_challenge_gets_the_five_attempt_cap_too(app, runtime_engine):
    b = Browser(app)
    await b.request_code(NON_ADMIN)
    for _ in range(5):
        await b.submit_code("00000000")
    failed = await rows(
        runtime_engine,
        "SELECT count(*) FROM admin.audit_log WHERE action = 'signin.code_failed' "
        "AND outcome = 'failure'",
    )
    denied = await rows(
        runtime_engine,
        "SELECT count(*) FROM admin.audit_log WHERE action = 'signin.code_failed' "
        "AND outcome = 'denied'",
    )
    assert failed[0][0] == 5
    await b.submit_code("00000000")
    after = await rows(
        runtime_engine,
        "SELECT count(*) FROM admin.audit_log WHERE action = 'signin.code_failed' "
        "AND outcome = 'denied'",
    )
    assert after[0][0] == denied[0][0] + 1  # the sixth is refused, as for an admin
    await b.aclose()


async def test_a_wrong_code_for_a_non_admin_never_counts_toward_the_breaker(
    portal, app, runtime_engine
):
    b = Browser(app)
    await b.request_code(NON_ADMIN)
    for _ in range(4):
        await b.submit_code("00000000")
    assert not (await portal.limiter.sign_in_pause()).paused
    keys = await rows(runtime_engine, "SELECT key FROM admin.attempts")
    real_key = portal.limiter._global_keys()[0]
    assert real_key not in {k[0] for k in keys}  # only the throwaway decoy counter moved
    await b.aclose()


# -- 2. bounded growth ----------------------------------------------------------


async def test_a_flood_of_login_requests_leaves_bounded_rows(portal, runtime_engine):
    cookies_seen = set()
    for i in range(600):  # the bound does not depend on the count
        result = await portal.signin.request_code(f"user{i}@example.net", "203.0.113.9", UA)
        cookies_seen.add(result.cookie)
    audit_rows = await rows(
        runtime_engine, "SELECT count(*) FROM admin.audit_log WHERE action = 'signin.code_requested'"
    )
    attempt_rows = await rows(runtime_engine, "SELECT count(*) FROM admin.attempts")
    assert audit_rows[0][0] <= 12  # 10 allowed + one sample of the blocked ones
    assert attempt_rows[0][0] <= 35  # address row, <= 10 x (pair + email) rows, one audit sample row
    assert len(cookies_seen) <= 11  # 10 fresh ids and one fixed id for everything blocked


async def test_blocked_requests_look_the_same_for_admin_and_other_addresses(portal):
    for i in range(10):
        await portal.signin.request_code(f"user{i}@example.net", "203.0.113.9", UA)
    a = await portal.signin.request_code(ADMIN, "203.0.113.9", UA)
    b = await portal.signin.request_code(NON_ADMIN, "203.0.113.9", UA)
    assert a.cookie == b.cookie and a.after == [] == b.after
    assert len(a.cookie) == len((await portal.signin.request_code(ADMIN, "203.0.113.50", UA)).cookie)


async def test_blocked_requests_run_the_same_statements(portal, runtime_engine):
    for i in range(10):
        await portal.signin.request_code(f"user{i}@example.net", "203.0.113.9", UA)
    await portal.signin.request_code("warm@example.net", "203.0.113.9", UA)  # first blocked
    counts = []
    for email in (ADMIN, NON_ADMIN):
        with Counter(runtime_engine) as c:
            await portal.signin.request_code(email, "203.0.113.9", UA)
        counts.append(c.count)
    assert counts[0] == counts[1]


# -- 3. the session cap under concurrency -------------------------------------------


async def test_parallel_sign_ins_never_exceed_three_live_sessions(portal):
    created = await asyncio.gather(
        *[portal.sessions.create(ADMIN, IP, UA) for _ in range(12)]
    )
    assert len(created) == 12
    assert len(await portal.sessions.list_live(ADMIN)) == 3


# -- 4. CSRF tokens do not survive a rotation --------------------------------------------


async def test_csrf_token_changes_when_the_session_token_rotates(app, portal):
    token, session = await portal.sessions.create(ADMIN, IP, UA)
    old_csrf = csrf.session_token(portal.csrf_key, session.csrf_subject)
    fresh = await portal.sessions.promote_to_mfa(session, token)
    current = (await portal.sessions.authenticate(fresh, IP, UA)).session
    new_csrf = csrf.session_token(portal.csrf_key, current.csrf_subject)
    assert current.id == session.id and new_csrf != old_csrf
    b = Browser(app)
    b.cookies[cookies.SESSION_COOKIE] = fresh
    path = "/api/sessions/revoke-others"
    assert (await b.post(path, json={}, headers={"x-csrf-token": old_csrf})).status_code == 403
    assert (await b.post(path, json={}, headers={"x-csrf-token": new_csrf})).status_code == 200
    await b.aclose()
