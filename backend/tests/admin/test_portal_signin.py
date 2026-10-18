"""Email-code sign-in on real Postgres: enumeration safety, code rules, audit."""

from __future__ import annotations

import re
from datetime import timedelta

import pytest
from sqlalchemy import text

from backend.admin.repositories import sessions as repo
from backend.admin.services import audit
from tests.admin.conftest import needs_postgres
from tests.admin.portal_fixtures import (
    ADMIN,
    OTHER_ADMIN,
    Browser,
    last_code,
    make_app,
    sign_in,
)

pytestmark = needs_postgres

NON_ADMIN = "stranger@example.net"


async def rows(engine, sql: str, **params):
    async with engine.connect() as conn:
        return (await conn.execute(text(sql), params)).all()


async def actions(engine):
    return [
        (r[0], r[1])
        for r in await rows(
            engine, "SELECT action, outcome FROM admin.audit_log ORDER BY seq"
        )
    ]


def shape(response) -> dict:
    """Everything an observer sees except secrets: status, header names,
    cookie attributes and lengths, body."""
    cookies = []
    for line in response.headers.get_list("set-cookie"):
        name, _, rest = line.partition("=")
        value, _, attrs = rest.partition(";")
        cookies.append((name, len(value), attrs))
    headers = sorted(
        k for k in response.headers.keys() if k not in ("set-cookie", "x-request-id")
    )
    return {
        "status": response.status_code,
        "headers": headers,
        "location": response.headers.get("location"),
        "length": response.headers.get("content-length"),
        "cookies": cookies,
        "body": response.content,
    }


async def test_login_answers_identically_for_admin_and_non_admin(app, transport):
    admin, stranger = Browser(app), Browser(app)
    a = await admin.request_code(ADMIN)
    s = await stranger.request_code(NON_ADMIN)
    assert shape(a) == shape(s)
    assert a.status_code == 303 and a.headers["location"] == "/login/code"
    assert transport.recipients == [ADMIN]  # mail only to the admin
    await admin.aclose()
    await stranger.aclose()


async def test_no_challenge_row_for_non_admin(app, runtime_engine, transport):
    b = Browser(app)
    await b.request_code(NON_ADMIN)
    await b.request_code("not-an-email")
    await b.request_code("x" * 1000 + "@example.org")
    assert await rows(runtime_engine, "SELECT 1 FROM admin.signin_challenges") == []
    assert transport.sent == []
    await b.request_code(ADMIN)
    assert len(await rows(runtime_engine, "SELECT 1 FROM admin.signin_challenges")) == 1
    await b.aclose()


async def test_non_admin_audit_holds_only_hmac_and_length(app, runtime_engine):
    b = Browser(app)
    await b.request_code("Typed.Secret@Example.net")
    entry = (
        await rows(
            runtime_engine,
            "SELECT actor_email, detail::text, ua FROM admin.audit_log "
            "WHERE action = 'signin.code_requested'",
        )
    )[0]
    assert entry[0] is None
    assert "typed" not in entry[1].lower() and "example.net" not in entry[1].lower()
    assert "email_hmac" in entry[1] and "email_len" in entry[1]
    await b.aclose()


async def test_email_case_and_space_do_not_matter(app, transport):
    b = Browser(app)
    await b.request_code("  ADMIN@Example.ORG ")
    assert transport.recipients == [ADMIN]
    await b.aclose()


async def test_happy_path_creates_email_ok_session_with_new_token(
    app, runtime_engine, transport
):
    b = Browser(app)
    await b.request_code(ADMIN)
    challenge_cookie = b.cookies["__Host-bcadmin-ch"]
    response = await b.submit_code(last_code(transport))
    session_cookie = b.cookies["__Host-bcadmin"]
    assert response.status_code == 303 and response.headers["location"] == "/mfa"
    assert session_cookie != challenge_cookie and session_cookie not in challenge_cookie
    assert "__Host-bcadmin-ch" not in b.cookies  # the challenge cookie is gone
    state = (await rows(runtime_engine, "SELECT mfa_state, email FROM admin.sessions"))[0]
    assert tuple(state) == ("email_ok", ADMIN)
    # the old challenge value is no session
    other = Browser(app)
    other.cookies["__Host-bcadmin"] = challenge_cookie
    r = await other.get("/mfa")
    assert r.status_code == 303 and r.headers["location"] == "/login"
    await b.aclose()
    await other.aclose()


async def test_wrong_code_gets_the_same_page_for_every_challenge(app, transport):
    admin, stranger = Browser(app), Browser(app)
    await admin.request_code(ADMIN)
    await stranger.request_code(NON_ADMIN)
    a = await admin.submit_code("00000000")
    s = await stranger.submit_code("00000000")
    assert a.status_code == s.status_code == 200
    strip = lambda r: re.sub(rb'value="[^"]+"', b"", r.content)  # noqa: E731
    assert strip(a) == strip(s) and b"did not work" in a.content
    await admin.aclose()
    await stranger.aclose()


@pytest.mark.parametrize("junk", ["", "1234", "abcdefgh", "1234567890", "٣٣٣٣٣٣٣٣"])
async def test_malformed_codes_are_refused(app, transport, junk):
    b = Browser(app)
    await b.request_code(ADMIN)
    r = await b.submit_code(junk)
    assert r.status_code == 200 and "__Host-bcadmin" not in b.cookies
    await b.aclose()


async def test_expired_code_fails(app, transport, clock):
    b = Browser(app)
    await b.request_code(ADMIN)
    code = last_code(transport)
    clock.advance(601)
    r = await b.submit_code(code)
    assert r.status_code == 200 and "__Host-bcadmin" not in b.cookies
    await b.aclose()


async def test_code_is_single_use(app, transport):
    b = Browser(app)
    await b.request_code(ADMIN)
    code = last_code(transport)
    cookie = b.cookies["__Host-bcadmin-ch"]
    assert (await b.submit_code(code)).status_code == 303
    again = Browser(app)
    again.cookies["__Host-bcadmin-ch"] = cookie
    r = await again.submit_code(code)
    assert r.status_code == 200 and "__Host-bcadmin" not in again.cookies
    await b.aclose()
    await again.aclose()


async def test_attempt_cap_is_five_even_for_the_right_code(app, transport):
    b = Browser(app)
    await b.request_code(ADMIN)
    code = last_code(transport)
    wrong = "00000000" if code != "00000000" else "11111111"
    for _ in range(5):
        await b.submit_code(wrong)
    r = await b.submit_code(code)
    assert r.status_code == 200 and "__Host-bcadmin" not in b.cookies
    await b.aclose()


async def test_new_request_kills_the_previous_code(app, transport):
    first, second = Browser(app), Browser(app)
    await first.request_code(ADMIN)
    old = last_code(transport)
    await second.request_code(ADMIN)
    new = last_code(transport)
    assert (await first.submit_code(old)).status_code == 200
    assert "__Host-bcadmin" not in first.cookies
    assert (await second.submit_code(new)).status_code == 303
    await first.aclose()
    await second.aclose()


async def test_cookie_that_was_not_issued_is_refused_cheaply(app, runtime_engine):
    b = Browser(app)
    b.cookies["__Host-bcadmin-ch"] = "11111111-1111-1111-1111-111111111111.abc"
    r = await b.submit_code("12345678")
    assert r.status_code == 200 and "__Host-bcadmin" not in b.cookies
    assert await actions(runtime_engine) == []  # nothing counted, nothing audited
    await b.aclose()


async def test_code_request_rate_limit_is_silent_and_counts_non_admins(
    app, transport, runtime_engine
):
    b = Browser(app)
    shapes = []
    for _ in range(5):
        shapes.append(shape(await b.request_code(ADMIN)))
    assert len({str(s) for s in shapes}) == 1  # same answer every time
    assert len(transport.sent) == 3  # 3 per 10 minutes per address
    # a non-admin address is limited the same way (no oracle in the limit)
    for _ in range(5):
        await b.request_code(NON_ADMIN)
    denied = await rows(
        runtime_engine,
        "SELECT detail->>'reason' FROM admin.audit_log WHERE outcome = 'denied'",
    )
    assert {r[0] for r in denied} == {"rate_limited", "not_admin"}
    await b.aclose()


async def test_five_wrong_codes_lock_the_admin_and_notify_everyone_once(
    app, transport, runtime_engine
):
    b = Browser(app)
    await b.request_code(ADMIN)
    code = last_code(transport)
    wrong = "00000000" if code != "00000000" else "11111111"
    for _ in range(5):
        await b.submit_code(wrong)
    notices = [m for m in transport.sent if "locked" in m.subject]
    assert len(notices) == 2  # one mail per listed admin, sent once
    assert sorted(transport.recipients[-2:]) == sorted([ADMIN, OTHER_ADMIN])
    # locked: a fresh challenge and its right code are refused too
    fresh = Browser(app)
    await fresh.request_code(ADMIN)
    r = await fresh.submit_code(last_code(transport))
    assert r.status_code == 200 and "__Host-bcadmin" not in fresh.cookies
    assert ("signin.locked", "denied") in await actions(runtime_engine)
    await b.aclose()
    await fresh.aclose()


async def test_breaker_pauses_sign_in_after_fifty_admin_failures(
    app, transport, portal, runtime_engine, clock
):
    # spread the failures over addresses so no single source hits the per-address cap
    for i in range(50):
        b = Browser(app, peer=f"127.0.0.{i % 10 + 1}")
        await b.request_code(ADMIN)
        await b.submit_code("00000000" if last_code(transport) != "00000000" else "1")
        await b.aclose()
        clock.advance(31)  # keeps each request under the code-request limits
    assert (await portal.limiter.sign_in_pause()).paused
    assert ("signin.breaker_tripped", "denied") in await actions(runtime_engine)


async def test_audit_rows_for_each_step_and_chain_verifies(
    app, transport, runtime_engine
):
    b = Browser(app)
    await b.request_code(ADMIN)
    await b.submit_code("00000000" if last_code(transport) != "00000000" else "1")
    await b.submit_code(last_code(transport))
    got = await actions(runtime_engine)
    assert ("signin.code_requested", "success") in got
    assert ("signin.code_failed", "failure") in got
    assert ("signin.code_verified", "success") in got
    assert ("session.created", "success") in got
    async with runtime_engine.connect() as conn:
        assert (await audit.verify_chain(conn, None)).ok
    # no code or token appears in any audit row
    dump = " ".join(
        r[0] for r in await rows(runtime_engine, "SELECT row_to_json(a)::text FROM admin.audit_log a")
    )
    assert b.cookies["__Host-bcadmin"] not in dump
    assert last_code(transport) not in dump
    await b.aclose()


async def test_challenge_cookie_attributes(app):
    b = Browser(app)
    await b.request_code(ADMIN)
    line = next(l for l in b.set_cookie_lines if l.startswith("__Host-bcadmin-ch="))
    low = line.lower()
    assert "secure" in low and "httponly" in low and "samesite=strict" in low
    assert "path=/" in low and "domain" not in low
    await b.aclose()


async def test_mail_failure_does_not_change_the_answer(
    app, transport, runtime_engine
):
    transport.fail = True
    b = Browser(app)
    r = await b.request_code(ADMIN)
    assert r.status_code == 303 and r.headers["location"] == "/login/code"
    await b.aclose()


async def test_admin_removed_before_verify_cannot_finish(
    app, make_portal, transport
):
    b = Browser(app)
    await b.request_code(ADMIN)
    code = last_code(transport)
    stricter = Browser(make_app(make_portal(admins=(OTHER_ADMIN,))))
    stricter.cookies = dict(b.cookies)
    r = await stricter.submit_code(code)
    assert r.status_code == 200 and "__Host-bcadmin" not in stricter.cookies
    await b.aclose()
    await stricter.aclose()


async def test_sign_in_helper_and_challenge_rows_helper(app, transport, runtime_engine):
    b = Browser(app)
    await sign_in(b, transport)
    async with runtime_engine.connect() as conn:
        assert await repo.count_challenges(conn) == 1
    await b.aclose()
    assert timedelta(0) == timedelta(0)
