"""Abuse of the email-code step by someone who only passes the address gate:
flooding with one challenge cookie, and locking the genuine admin out."""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from backend.admin.asgi import get_admin_application
from backend.admin.gate.settings import GateSettings
from tests.admin.conftest import needs_postgres
from tests.admin.portal_fixtures import ADMIN, OTHER_ADMIN, Browser, last_code
from tests.admin.test_portal_hardening import Counter

pytestmark = needs_postgres

NON_ADMIN = "stranger@example.net"
IP_A, IP_B = "127.0.0.1", "127.0.0.2"
GATEWAY = "172.30.77.1"


async def count(engine, sql: str) -> int:
    async with engine.connect() as conn:
        return int((await conn.execute(text(sql))).scalar_one())


def two_addresses(portal):
    return get_admin_application(
        GateSettings.from_env({"ADMIN_ALLOWED_IPS": f"{IP_A},{IP_B}"}), portal=portal
    )


def behind_gateway(portal):
    return get_admin_application(
        GateSettings.from_env({"ADMIN_EDGE_GATEWAY": GATEWAY}), portal=portal
    )


async def issue(portal, email: str, ip: str) -> str:
    """A code request through the service, mail sent as the route would."""
    result = await portal.signin.request_code(email, ip, "ua")
    for job in result.after:
        await job()
    return result.cookie


async def fixed_form(b: Browser):
    """``(token, headers)`` that keep the same challenge and CSRF cookies on every
    post, like a script replaying one cookie jar."""
    token = await b.form_token("/login/code")
    jar = f"__Host-bcadmin-ch={b.cookies['__Host-bcadmin-ch']}; __Host-bcadmin-csrf={b.cookies['__Host-bcadmin-csrf']}"
    return token, {"cookie": jar}


def wrong_for(code: str) -> str:
    return "00000000" if code != "00000000" else "11111111"


# -- WEB-01: a flood against one cookie ----------------------------------------------


async def test_flood_with_one_cookie_does_not_grow_the_audit_log(
    app, transport, runtime_engine
):
    b = Browser(app)
    await b.request_code(ADMIN)
    wrong = wrong_for(last_code(transport))
    token, jar = await fixed_form(b)
    before = await count(runtime_engine, "SELECT count(*) FROM admin.audit_log")
    for _ in range(300):
        r = await b.post("/login/code", data={"code": wrong, "csrf_token": token}, headers=jar)
        assert r.status_code == 200
    grown = await count(runtime_engine, "SELECT count(*) FROM admin.audit_log") - before
    # five counted attempts (one failure row each), the lock row and one
    # aggregated refusal row; never one row per request
    assert grown <= 9, grown
    refused = await count(
        runtime_engine,
        "SELECT count(*) FROM admin.audit_log WHERE detail->>'reason' IN "
        "('attempts','locked','paused')",
    )
    assert refused <= 1
    await b.aclose()


async def test_posts_past_the_per_challenge_cap_do_no_database_work(
    app, transport, runtime_engine
):
    b = Browser(app)
    await b.request_code(ADMIN)
    wrong = wrong_for(last_code(transport))
    token, jar = await fixed_form(b)
    for _ in range(12):
        await b.post("/login/code", data={"code": wrong, "csrf_token": token}, headers=jar)
    with Counter(runtime_engine) as c:
        r = await b.post("/login/code", data={"code": wrong, "csrf_token": token}, headers=jar)
    assert r.status_code == 200 and b"did not work" in r.content
    assert c.count == 0, c.statements  # refused in memory, before any statement
    await b.aclose()


async def test_parallel_flood_neither_exhausts_the_pool_nor_floods_the_log(
    app, transport, runtime_engine
):
    b = Browser(app)
    await b.request_code(ADMIN)
    wrong = wrong_for(last_code(transport))
    token, jar = await fixed_form(b)
    before = await count(runtime_engine, "SELECT count(*) FROM admin.audit_log")
    results = await asyncio.gather(
        *[
            b.post("/login/code", data={"code": wrong, "csrf_token": token}, headers=jar)
            for _ in range(150)
        ]
    )
    assert {r.status_code for r in results} == {200}
    grown = await count(runtime_engine, "SELECT count(*) FROM admin.audit_log") - before
    assert grown <= 9, grown
    # the service still answers a genuine sign-in afterwards
    other = Browser(app, peer="127.0.0.1")
    await other.request_code(OTHER_ADMIN)
    assert (await other.submit_code(last_code(transport))).status_code == 303
    await b.aclose()
    await other.aclose()


async def test_a_legitimate_challenge_is_untouched_by_a_dead_one(app, transport):
    spam, genuine = Browser(app), Browser(app)
    await spam.request_code(ADMIN)
    wrong = wrong_for(last_code(transport))
    for _ in range(20):
        await spam.submit_code(wrong)
    await genuine.request_code(OTHER_ADMIN)  # a different email, same address
    assert (await genuine.submit_code(last_code(transport))).status_code == 303
    await spam.aclose()
    await genuine.aclose()


async def test_refused_branch_runs_the_same_statements_for_admin_and_non_admin(
    portal, runtime_engine, transport
):
    counts = {}
    for label, email in (("admin", ADMIN), ("other", NON_ADMIN)):
        cookie = (await portal.signin.request_code(email, IP_A, "ua")).cookie
        for _ in range(5):  # use up the attempts
            await portal.signin.verify_code(cookie, "00000000", IP_A, "ua")
        seen = []
        for _ in range(2):  # the first refusal and a repeat
            with Counter(runtime_engine) as c:
                await portal.signin.verify_code(cookie, "00000000", IP_A, "ua")
            seen.append(c.count)
        counts[label] = seen
    assert counts["admin"] == counts["other"], counts


# -- WEB-02: locking the genuine admin out ------------------------------------------


async def test_five_wrong_codes_from_one_address_do_not_lock_the_admin_elsewhere(
    portal, transport, runtime_engine
):
    app = two_addresses(portal)
    attacker, admin = Browser(app, peer=IP_B), Browser(app, peer=IP_A)
    await attacker.request_code(ADMIN)
    wrong = wrong_for(last_code(transport))
    for _ in range(6):
        await attacker.submit_code(wrong)
    # the attacker's own address is refused for this email, even with a fresh code
    await attacker.request_code(ADMIN)
    assert (await attacker.submit_code(last_code(transport))).status_code == 200
    # the admin, from a different address, requests a code and signs in
    await admin.request_code(ADMIN)
    assert (await admin.submit_code(last_code(transport))).status_code == 303
    assert "__Host-bcadmin" in admin.cookies
    # and the second factor's own lock was never touched
    assert not (await portal.limiter.lock_status(ADMIN)).locked
    await attacker.aclose()
    await admin.aclose()


async def test_email_step_failures_never_count_against_the_second_factor(
    portal, transport
):
    app = two_addresses(portal)
    attacker = Browser(app, peer=IP_B)
    await attacker.request_code(ADMIN)
    wrong = wrong_for(last_code(transport))
    for _ in range(6):
        await attacker.submit_code(wrong)
    assert not (await portal.limiter.lock_status(ADMIN)).locked
    reserved = await portal.limiter.factor_attempt(ADMIN)
    assert reserved.count == 1  # no guess at the factor was used up
    await attacker.aclose()


async def test_lockout_mail_is_not_an_amplifier(portal, transport):
    app = two_addresses(portal)
    for peer in (IP_A, IP_B):
        b = Browser(app, peer=peer)
        await b.request_code(ADMIN)
        wrong = wrong_for(last_code(transport))
        for _ in range(5):
            await b.submit_code(wrong)
        await b.aclose()
    notices = [m for m in transport.sent if "locked" in m.subject]
    assert len(notices) == 2  # one set of mails for both addresses within the hour


async def test_failures_across_many_addresses_raise_an_alert_but_no_lock(
    portal, transport, runtime_engine
):
    for n in range(6):  # six addresses, five wrong codes each: the 30th trips the alert
        ip = f"203.0.113.{n}"
        cookie = await issue(portal, ADMIN, ip)
        for _ in range(5):
            check = await portal.signin.verify_code(cookie, "00000000", ip, "ua")
            for job in check.after:
                await job()
    surge = await count(
        runtime_engine, "SELECT count(*) FROM admin.audit_log WHERE action = 'signin.failure_surge'"
    )
    assert surge == 1
    assert any("many wrong" in m.subject for m in transport.sent)
    assert not (await portal.limiter.lock_status(ADMIN)).locked
    # a seventh, unrelated address still signs in with a valid code
    ip = "203.0.113.77"
    cookie = await issue(portal, ADMIN, ip)
    check = await portal.signin.verify_code(cookie, last_code(transport), ip, "ua")
    assert check.ok


async def test_brute_force_of_one_challenge_still_stops_at_five(portal, transport):
    cookie = await issue(portal, ADMIN, IP_A)
    real = last_code(transport)
    for _ in range(5):
        await portal.signin.verify_code(cookie, wrong_for(real), IP_A, "ua")
    assert not (await portal.signin.verify_code(cookie, real, IP_A, "ua")).ok


async def test_behind_the_gateway_a_noisy_client_cannot_lock_the_admin(
    portal, transport
):
    app = behind_gateway(portal)
    noisy, admin = Browser(app, peer=GATEWAY), Browser(app, peer=GATEWAY)
    await noisy.request_code(ADMIN)
    wrong = wrong_for(last_code(transport))
    for _ in range(8):
        await noisy.submit_code(wrong)
    # every client looks alike here, so no (email, address) lock is applied; the
    # genuine admin still gets a code and signs in
    await admin.request_code(ADMIN)
    assert (await admin.submit_code(last_code(transport))).status_code == 303
    await noisy.aclose()
    await admin.aclose()


async def test_behind_the_gateway_other_emails_do_not_use_up_the_admins_requests(
    portal, transport
):
    app = behind_gateway(portal)
    noisy, admin = Browser(app, peer=GATEWAY), Browser(app, peer=GATEWAY)
    for n in range(25):
        await noisy.request_code(f"nobody{n}@example.net")
    await admin.request_code(ADMIN)
    assert transport.recipients == [ADMIN]
    await noisy.aclose()
    await admin.aclose()
