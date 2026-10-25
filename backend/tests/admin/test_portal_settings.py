"""The portal's settings pages through the HTTP layer on real Postgres: gate,
CSRF, the prepare/apply step-up flow, every tier, secrets never leaking,
history, integrity and the notification outbox."""

from __future__ import annotations

import json
import logging
import re
from html import unescape
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text

import backend.admin as admin_package
from backend.admin import cookies
from backend.admin.controllers.portal import build_registry
from backend.admin.gate import stepup as step
from backend.admin.gate.levels import LEVEL_ATTR, Level
from backend.admin.headers import CONTENT_SECURITY_POLICY
from backend.admin.security import totp
from backend.admin.services import settings_pages as sp
from backend.admin.services.settings_store import HISTORY_KEEP
from tests.admin.engines import fixture_engine
from tests.admin.conftest import needs_postgres
from tests.admin.portal_fixtures import ADMIN, TOKEN_RE, UA, Browser
from tests.admin.test_portal_mfa import enrol_direct
from tests.admin.test_portal_pages import Structure
from tests.admin.test_settings_store import PLANT

pytestmark = needs_postgres


@pytest_asyncio.fixture(loop_scope="session")
async def superuser(server, migrated):
    engine = fixture_engine(server.url(migrated))
    yield engine
    await engine.dispose()

T1 = "API_FLOW_EVENTS_PER_WINDOW"  # T1, int, hot
T2 = "AI_DEFAULT_PROVIDER"  # T2, enum
T2_SECRET = "AI_COMPAT_API_KEY"  # T2, secret
T3 = "SSO_POLIS_PRODUCT"  # T3, text
T3_SECRET = "SSO_POLIS_API_KEY"  # T3, secret
T4 = "AUTH_JWT_SECRET"
T5 = "DATABASE_URL"
PENDING_RE = re.compile(r'name="pending" value="([^"]+)"')
STEP_RE = re.compile(r'name="stepup_token" value="([^"]+)"')
NOTICE_RE = re.compile(r"[?&]notice=([a-z_]+)")
SECRETS = [
    PLANT,
    "Zk4!planted-A1b2C3d4E5f6G7h8",
    "q" * 60 + "-planted-tail-0987654321",
    "sk-live-ABCDEF0123456789abcdef0123456789",
]


class Admin:
    def __init__(self, browser: Browser, secret: str, clock, portal):
        self.b, self.totp_secret, self.clock, self.portal = browser, secret, clock, portal
        self.seen: list[str] = []  # every response body, header value and location

    def code(self) -> str:
        self.clock.advance(31)
        return totp.code_at(self.totp_secret, self.clock.time())

    def note(self, response):
        self.seen.append(response.text)
        self.seen.append(str(response.url))
        self.seen.append(response.headers.get("location", ""))
        self.seen.append(str(dict(response.headers)))
        return response

    async def get(self, path, **kw):
        return self.note(await self.b.get(path, **kw))

    async def csrf(self, path="/settings") -> str:
        return TOKEN_RE.search((await self.b.get(path)).text).group(1)

    async def version(self, key: str) -> int:
        detail = await self.portal.settings_pages.detail(key)
        return detail.version

    async def prepare(self, key, action, *, value=None, version=None, confirmation=None,
                      code=None, extra=None, csrf=None):
        data = {
            "csrf_token": csrf or await self.csrf(),
            "action": action,
            "expected_version": str(await self.version(key) if version is None else version),
            "code": code or self.code(),
        }
        if value is not None:
            data["value"] = value
        if confirmation is not None:
            data["confirmation"] = confirmation
        data.update(extra or {})
        return self.note(await self.b.post(f"/settings/{key}/prepare", data=data))

    async def apply(self, key, response, url_name, *, extra=None, csrf=None, drop=()):
        """Submit the apply page that ``response`` is."""
        html = response.text
        assert response.status_code == 200 and "Apply the change" in html, html[:300]
        data = {"csrf_token": csrf or TOKEN_RE.search(html).group(1)}
        for name in ("stepup_token", "expected_version", "confirmation", "pending", "version"):
            m = re.search(rf'name="{name}" value="([^"]*)"', html)
            if m and name not in drop:
                data[name] = unescape(m.group(1))
        data.update(extra or {})
        return self.note(await self.b.post(f"/settings/{key}/{url_name}", data=data))

    async def change(self, key, action, url_name, **kw):
        prepared = await self.prepare(key, action, **kw)
        done = await self.apply(key, prepared, url_name)
        assert done.status_code == 303, done.text[:300]
        return done


@pytest.fixture
async def admin(portal, app, clock):
    secret, _, token, _ = await enrol_direct(portal, clock)
    b = Browser(app)
    b.cookies[cookies.SESSION_COOKIE] = token
    yield Admin(b, secret, clock, portal)
    await b.aclose()


def notice_of(response) -> str:
    return NOTICE_RE.search(response.headers["location"]).group(1)


async def audit_text(engine) -> str:
    async with engine.connect() as conn:
        rows = (await conn.execute(text(
            "SELECT action, target_id, before::text, after::text, detail::text, ip::text FROM admin.audit_log"
        ))).all()
    return json.dumps([list(map(str, r)) for r in rows])


async def one(engine, sql, **params):
    async with engine.connect() as conn:
        return (await conn.execute(text(sql), params)).first()


# -- route table ------------------------------------------------------------------------
def settings_routes():
    return [r for r in build_registry().router.routes if r.path.startswith("/settings")]


def test_every_mutating_settings_route_is_action_bound_or_documented():
    exempt, bound = {}, {}
    for r in settings_routes():
        assert getattr(r.endpoint, LEVEL_ATTR) is Level.SECOND_FACTOR, r.path
        if set(r.methods) <= step.SAFE_METHODS:
            continue
        spec = getattr(r.endpoint, step.STEPUP_ATTR, None)
        if isinstance(spec, step.ActionBound):
            bound[r.path] = spec.name
        else:
            exempt[r.path] = getattr(r.endpoint, step.EXEMPT_ATTR, None)
    assert set(exempt) == {"/settings/{key}/prepare", "/settings/integrity/run"}
    assert all(isinstance(why, str) and len(why) > 20 for why in exempt.values())
    assert bound == {
        "/settings/{key}/set": "settings.set",
        "/settings/{key}/clear": "settings.clear",
        "/settings/{key}/restore": "settings.restore",
        "/settings/{key}/purge-history": "settings.purge_history",
    }
    assert step.undeclared_mutating_routes(build_registry().router.routes, ("/settings", "/tasks")) == []


GETS = ["/settings", "/settings/integrity", "/settings/notifications", f"/settings/{T1}", f"/settings/{T1}/history"]
POSTS = [f"/settings/{T1}/{n}" for n in ("prepare", "set", "clear", "restore", "purge-history")] + [
    "/settings/integrity/run"
]


@pytest.mark.parametrize("path", GETS)
async def test_pages_refused_below_second_factor_and_for_non_admins(portal, app, path):
    anon = Browser(app)
    half_token, _ = await portal.sessions.create(ADMIN, "127.0.0.1", UA, mfa_state="email_ok")
    half = Browser(app)
    half.cookies[cookies.SESSION_COOKIE] = half_token
    stranger_token, _ = await portal.sessions.create("stranger@example.org", "127.0.0.1", UA, mfa_state="mfa_ok")
    stranger = Browser(app)
    stranger.cookies[cookies.SESSION_COOKIE] = stranger_token
    for b in (anon, half, stranger):
        response = await b.get(path)
        assert response.status_code in (303, 404, 401), (path, response.status_code)
        assert "<h1" not in response.text
        await b.aclose()


@pytest.mark.parametrize("path", POSTS)
async def test_posts_refused_below_second_factor(portal, app, path):
    half_token, session = await portal.sessions.create(ADMIN, "127.0.0.1", UA, mfa_state="email_ok")
    half = Browser(app)
    half.cookies[cookies.SESSION_COOKIE] = half_token
    from backend.admin.security import csrf

    token = csrf.session_token(portal.csrf_key, session.csrf_subject)
    for b in (Browser(app), half):
        response = await b.post(path, data={"csrf_token": token, "action": "set", "value": "1"})
        assert response.status_code in (303, 404, 401, 403)
        assert "Apply the change" not in response.text
        await b.aclose()


@pytest.mark.parametrize("path", POSTS)
async def test_every_post_needs_the_csrf_token(admin, path):
    for data in ({}, {"csrf_token": "forged"}):
        response = await admin.b.post(path, data={**data, "action": "set", "value": "5"})
        assert response.status_code == 403
    assert await admin.version(T1) == 0


# -- the flow, per tier ----------------------------------------------------------------
async def test_t1_set_clear_restore_end_to_end(admin, portal, runtime_engine):
    done = await admin.change(T1, "set", "set", value="200")
    assert done.headers["location"] == f"/settings/{T1}?notice=done_set"
    page = await admin.get(f"/settings/{T1}")
    assert "<code>200</code>" in page.text and "The setting was changed." not in page.text
    await admin.change(T1, "set", "set", value="300")
    first = await admin.get(f"/settings/{T1}?notice=done_set")
    assert "The setting was changed." in first.text
    history = await admin.get(f"/settings/{T1}/history?restore=1")
    assert "Restore version 1" in history.text and "<code>200</code>" in history.text
    done = await admin.change(T1, "restore", "restore", extra={"version": "1"})
    assert done.headers["location"].endswith("done_restore")
    row = await one(runtime_engine, "SELECT value::text, version FROM settings.entries WHERE key=:k", k=T1)
    assert row.value == "200" and row.version == 3
    await admin.change(T1, "clear", "clear")
    row = await one(runtime_engine, "SELECT cleared, version FROM settings.entries WHERE key=:k", k=T1)
    assert row.cleared and row.version == 4
    log = await audit_text(runtime_engine)
    for name in ("settings.set", "settings.restore", "settings.clear", "mfa.stepup"):
        assert name in log


async def test_unchanged_value_says_so(admin):
    await admin.change(T1, "set", "set", value="150")
    done = await admin.change(T1, "set", "set", value="150")
    assert done.headers["location"].endswith("no_change")


async def test_t2_change_queues_a_notification_listed_in_the_portal(admin, runtime_engine):
    await admin.change(T2, "set", "set", value="google")
    row = await one(runtime_engine, "SELECT kind, payload::text AS p FROM admin.notifications")
    assert row.kind == "settings.changed" and "google" not in row.p
    page = await admin.get("/settings/notifications")
    assert page.status_code == 200 and T2 in page.text and "pending" in page.text and "google" not in page.text


async def test_t3_needs_the_typed_confirmation(admin, runtime_engine):
    wrong = await admin.prepare(T3, "set", value="acme", confirmation="nope")
    assert wrong.status_code == 400 and "Type the setting name exactly" in wrong.text
    assert 'name="pending"' in wrong.text  # the value is held sealed, nothing to retype
    assert await admin.version(T3) == 0
    right = await admin.prepare(T3, "set", value="acme", confirmation=T3)
    done = await admin.apply(T3, right, "set")
    assert done.status_code == 303 and done.headers["location"].endswith("done_set")
    # the confirm form continues from the sealed value
    held = await admin.prepare(T3, "set", value="acme2", confirmation="x")
    pending = PENDING_RE.search(held.text).group(1)
    again = await admin.prepare(T3, "set", extra={"pending": pending}, confirmation=T3)
    assert (await admin.apply(T3, again, "set")).headers["location"].endswith("done_set")
    assert (await one(runtime_engine, "SELECT value::text AS v FROM settings.entries WHERE key=:k", k=T3)).v == '"acme2"'


async def test_a_wrong_code_changes_nothing_and_keeps_the_sealed_value(admin):
    response = await admin.prepare(T2_SECRET, "set", value=SECRETS[1], code="00000000")
    assert response.status_code == 200 and "That code was not accepted" in response.text
    assert 'name="pending"' in response.text and SECRETS[1] not in response.text
    assert await admin.version(T2_SECRET) == 0
    await admin.change(T1, "set", "set", value="9")
    plain = await admin.prepare(T1, "clear", code="00000000")
    assert plain.status_code == 303 and notice_of(plain) == "wrong_code"
    assert await admin.version(T1) == 1


async def test_secret_set_clear_restore_purge(admin, runtime_engine):
    for n in range(HISTORY_KEEP + 2):
        await admin.change(T2_SECRET, "set", "set", value=f"{SECRETS[n % 4]}-{n}")
    detail = await admin.get(f"/settings/{T2_SECRET}")
    assert re.search(r"<dd>\s*set\s*(<span|</dd>)", detail.text) and 'type="password"' in detail.text
    assert 'name="value" type="password" required' in detail.text and 'value="' not in detail.text.split('id="value"')[1].split(">")[0]
    history = await admin.get(f"/settings/{T2_SECRET}/history")
    held = (await one(runtime_engine, "SELECT count(*) AS n FROM settings.history WHERE key=:k", k=T2_SECRET)).n
    assert held == HISTORY_KEEP and f"Only the last {HISTORY_KEEP}" in history.text
    assert "Purge secret history" in history.text
    old = await one(runtime_engine, "SELECT min(version) AS v FROM settings.history WHERE key=:k", k=T2_SECRET)
    done = await admin.change(T2_SECRET, "restore", "restore", extra={"version": str(old.v)})
    assert done.headers["location"].endswith("done_restore")
    purge = await admin.prepare(T2_SECRET, "purge_history", extra={"confirm_purge": "yes"})
    assert (await admin.apply(T2_SECRET, purge, "purge-history")).headers["location"].endswith("done_purge")
    held = (await one(runtime_engine, "SELECT count(*) AS n FROM settings.history WHERE key=:k", k=T2_SECRET)).n
    assert held == 1
    await admin.change(T2_SECRET, "clear", "clear")
    after = await admin.get(f"/settings/{T2_SECRET}")
    assert "(cleared)" in after.text


async def test_purge_needs_its_checkbox_and_a_secret(admin):
    await admin.change(T2_SECRET, "set", "set", value=SECRETS[0])
    no_box = await admin.prepare(T2_SECRET, "purge_history")
    assert no_box.status_code == 303 and notice_of(no_box) == "purge_unconfirmed"
    plain = await admin.prepare(T1, "purge_history", extra={"confirm_purge": "yes"})
    assert notice_of(plain) == "not_secret"


async def test_t4_t5_and_unknown_keys_are_refused_with_the_right_message(admin):
    for key, code, words in (
        (T4, "managed_by_task", "maintenance task"),
        (T5, "env_only", "environment only"),
        ("NOT_A_SETTING_AT_ALL", "unknown_key", "no such setting"),
    ):
        for action in sp.ACTIONS:
            r = await admin.prepare(key, action, value="x", version=0, extra={"confirm_purge": "yes"})
            assert r.status_code == 303 and notice_of(r) == code, (key, action)
        landed = await admin.get(r.headers["location"])
        assert words in landed.text
    page = await admin.get(f"/settings/{T4}")
    assert page.status_code == 200 and "<form" not in page.text.split("<main")[1].replace('action="/logout"', "")
    listing = await admin.get("/settings")
    assert "Rotate…" in listing.text and "environment only" in listing.text
    assert (await admin.get("/settings/not-a-key")).status_code == 303


async def test_stale_versions_are_refused_before_and_after_the_code(admin, runtime_engine):
    await admin.change(T1, "set", "set", value="10")
    old = await admin.version(T1)
    await admin.change(T1, "set", "set", value="11")
    early = await admin.prepare(T1, "set", value="12", version=old)
    assert early.status_code == 303 and notice_of(early) == "stale_version"
    prepared = await admin.prepare(T1, "set", value="13")
    await admin.change(T1, "set", "set", value="14")  # someone else changes it meanwhile
    done = await admin.apply(T1, prepared, "set")
    assert done.status_code == 303 and notice_of(done) in ("step_up_invalid", "stale_version")
    assert (await one(runtime_engine, "SELECT value::text AS v FROM settings.entries WHERE key=:k", k=T1)).v == "14"


async def test_invalid_values_are_explained_without_echoing_secrets(admin):
    r = await admin.prepare(T1, "set", value="not-a-number")
    assert r.status_code == 400 and "expected" in r.text and 'value="not-a-number"' in r.text
    out = await admin.prepare(T1, "set", value="99999999")
    assert out.status_code == 400 and "at most" in out.text
    for bad in (f"  {PLANT}  ", f'"{PLANT}"', ""):
        r = await admin.prepare(T3_SECRET, "set", value=bad, confirmation=T3_SECRET)
        assert r.status_code == 400 and "was not accepted" in r.text
        assert PLANT not in r.text and 'type="password"' in r.text


# -- tokens: action-bound and replay-safe ---------------------------------------------------
async def test_apply_without_a_token_is_refused_and_changes_nothing(admin):
    t = await admin.csrf()
    for url, extra in (("set", {"pending": "x"}), ("clear", {}), ("restore", {"version": "1"}), ("purge-history", {})):
        r = await admin.b.post(
            f"/settings/{T1}/{url}", data={"csrf_token": t, "expected_version": "0", **extra}
        )
        assert r.status_code == 303 and notice_of(r) == "step_up_invalid"
    assert await admin.version(T1) == 0


async def test_a_token_is_single_use(admin):
    prepared = await admin.prepare(T1, "set", value="21")
    first = await admin.apply(T1, prepared, "set")
    assert notice_of(first) == "done_set"
    replay = await admin.apply(T1, prepared, "set")
    assert notice_of(replay) == "step_up_invalid"
    assert await admin.version(T1) == 1


async def test_a_token_is_bound_to_key_value_version_and_action(admin):
    prepared = await admin.prepare(T1, "set", value="31")
    other = await admin.prepare(T1, "set", value="32")
    # another key
    wrong_key = await admin.apply("API_FLOW_EVENTS_WINDOW_SECONDS", prepared, "set")
    assert notice_of(wrong_key) == "step_up_invalid"
    # another value: the token of one prepare with the sealed value of another
    swapped = await admin.apply(
        T1, prepared, "set", extra={"pending": PENDING_RE.search(other.text).group(1)}
    )
    assert notice_of(swapped) == "step_up_invalid"
    # another version
    stale = await admin.apply(T1, prepared, "set", extra={"expected_version": "5"})
    assert notice_of(stale) == "step_up_invalid"
    # another action
    cleared = await admin.apply(T1, prepared, "clear")
    assert notice_of(cleared) == "step_up_invalid"
    # a tampered or missing sealed value
    broken = await admin.apply(T1, prepared, "set", extra={"pending": "1.a.b"})
    assert notice_of(broken) == "step_up_invalid"
    missing = await admin.apply(T1, prepared, "set", drop=("pending",))
    assert notice_of(missing) == "step_up_invalid"
    assert await admin.version(T1) == 0
    assert notice_of(await admin.apply(T1, prepared, "set")) == "done_set"  # still good for the real thing


async def test_a_token_expires(admin, clock):
    prepared = await admin.prepare(T1, "set", value="41")
    clock.advance(sp.PENDING_SECONDS + 5)
    assert notice_of(await admin.apply(T1, prepared, "set")) == "step_up_invalid"
    assert await admin.version(T1) == 0


async def test_api_stepup_cannot_mint_these_tokens(admin):
    token = await admin.csrf()
    r = await admin.b.post(
        "/api/stepup", json={"code": admin.code(), "action": "settings.set", "parts": [T1, "0" * 64]},
        headers={"x-csrf-token": token},
    )
    t = r.json().get("token")
    if t:  # a token exists, but it cannot match the keyed hash the route computes
        post = await admin.b.post(
            f"/settings/{T1}/set",
            data={"csrf_token": token, "expected_version": "0", "pending": "x", "stepup_token": t},
        )
        assert notice_of(post) == "step_up_invalid"
    assert await admin.version(T1) == 0


# -- secrets never leak -------------------------------------------------------------------------
async def test_planted_secrets_never_reach_a_response_url_log_or_audit_row(admin, runtime_engine, caplog):
    caplog.set_level(logging.DEBUG)
    for n, value in enumerate(SECRETS):
        key = (T2_SECRET, T3_SECRET)[n % 2]
        conf = key if key == T3_SECRET else None
        r = await admin.prepare(key, "set", value=value, confirmation=conf, code="00000000")  # wrong code
        assert "Authenticator" in r.text
        await admin.prepare(key, "set", value=value, confirmation="wrong" if conf else None)  # wrong confirm
        await admin.prepare(key, "set", value=value, version=99)  # stale
        await admin.change(key, "set", "set", value=value, confirmation=conf)
        await admin.change(key, "set", "set", value=value + "-2", confirmation=conf)
        await admin.get(f"/settings/{key}")
        await admin.get(f"/settings/{key}/history?restore=1")
        old = await one(runtime_engine, "SELECT min(version) AS v FROM settings.history WHERE key=:k", k=key)
        await admin.change(key, "restore", "restore", extra={"version": str(old.v)}, confirmation=conf)
        await admin.prepare(key, "set", value="  " + value, confirmation=conf)  # invalid
        await admin.change(key, "clear", "clear", confirmation=conf)
        for path in ("/settings", "/config", f"/settings/{key}/history", "/settings/notifications", "/audit?limit=200"):
            await admin.get(path)
    blob = "\n".join(admin.seen) + "\n" + await audit_text(runtime_engine) + "\n" + caplog.text
    for value in SECRETS:
        assert value not in blob, value[:12]
        assert value[:12] not in blob
    assert "v2:" not in blob
    pend = await one(runtime_engine, "SELECT payload::text AS p FROM admin.notifications LIMIT 1")
    assert all(v not in pend.p for v in SECRETS)


async def test_non_secret_values_are_escaped(admin):
    xss = '<img src=x onerror=alert(1)>"\'&'
    await admin.change(T3, "set", "set", value=xss, confirmation=T3)
    for path in (f"/settings/{T3}", "/settings", f"/settings/{T3}/history", "/config"):
        html = (await admin.get(path)).text
        assert "<img src=x" not in html and "onerror=alert(1)>" not in html.replace("&gt;", ">") or "&lt;img" in html
        assert "&lt;img" in html
    prepared = await admin.prepare(T3, "set", value=xss + "2", confirmation=T3)
    assert "<img" not in prepared.text and "&lt;img" in prepared.text
    bad = await admin.prepare(T1, "set", value='"><script>alert(1)</script>')
    assert "<script>" not in bad.text and "&lt;script&gt;" in bad.text


# -- badges, detail, history ------------------------------------------------------------------------
async def test_override_and_restart_badges_and_reload_text(admin, superuser):
    await admin.change(T1, "set", "set", value="500")
    await admin.change(T2, "set", "set", value="google")
    async with superuser.begin() as conn:
        await conn.execute(text(
            "INSERT INTO settings.service_state (service, instance, revision_applied, env_overrides, "
            "restart_pending) VALUES ('backend', 'b1', 1, ARRAY[:k], true)"
        ), {"k": T1})
    listing = (await admin.get("/settings")).text
    row1 = re.search(rf"<code>{T1}</code>.*?</tr>", listing, re.S).group(0)
    assert "overridden by environment" in row1
    row2 = re.search(rf"<code>{T2}</code>.*?</tr>", listing, re.S).group(0)
    assert "restart required" in row2
    d1 = (await admin.get(f"/settings/{T1}")).text
    assert "overridden by environment" in d1 and "Applies live" in d1
    d2 = (await admin.get(f"/settings/{T2}")).text
    assert "Applies after restart" in d2 and "restart required" in d2
    assert 'name="expected_version" value="1"' in d2 and "<select" in d2


async def test_typed_fields_per_setting_type(admin):
    page = (await admin.get(f"/settings/{T1}")).text
    assert 'type="number"' in page and 'min="1"' in page and 'max="100000"' in page
    url = (await admin.get("/settings/AI_COMPAT_BASE_URL")).text
    assert 'type="url"' in url and "Type exactly:" in url
    secret = (await admin.get(f"/settings/{T3_SECRET}")).text
    assert 'type="password"' in secret and 'autocomplete="new-password"' in secret


async def test_history_shows_markers_for_secrets_and_values_otherwise(admin):
    await admin.change(T2_SECRET, "set", "set", value=SECRETS[0])
    await admin.change(T2_SECRET, "clear", "clear")
    await admin.change(T1, "set", "set", value="61")
    await admin.change(T1, "set", "set", value="62")
    secret = (await admin.get(f"/settings/{T2_SECRET}/history")).text
    assert "cleared" in secret and SECRETS[0] not in secret and "<code>" not in secret.split("<tbody>")[1]
    plain = (await admin.get(f"/settings/{T1}/history")).text
    assert "<code>61</code>" in plain and "<code>62</code>" in plain and "current" in plain
    assert plain.count("Restore this version") == 1  # only the older version; the current one is not restorable
    cleared_restore = await admin.get(f"/settings/{T2_SECRET}/history?restore=1")
    assert "Restore version 1" in cleared_restore.text


# -- integrity -----------------------------------------------------------------------------------------
async def test_integrity_run_lists_a_corrupted_row_by_key_and_reason_only(admin, superuser):
    await admin.change(T1, "set", "set", value="71")
    clean = await admin.b.post("/settings/integrity/run", data={"csrf_token": await admin.csrf()})
    assert clean.status_code == 200 and "no problems found" in clean.text
    async with superuser.begin() as conn:
        await conn.execute(text("SET LOCAL session_replication_role = replica"))
        await conn.execute(text("UPDATE settings.entries SET value = to_jsonb(99999) WHERE key = :k"), {"k": T1})
    dirty = admin.note(await admin.b.post("/settings/integrity/run", data={"csrf_token": await admin.csrf()}))
    assert dirty.status_code == 200 and T1 in dirty.text and "bad_signature" in dirty.text
    problems = re.sub(r"<[^>]*>", "", dirty.text.split("<tbody>")[1].split("</tbody>")[0])
    assert "99999" not in dirty.text and "71" not in problems and "bad_signature" in problems
    banner = (await admin.get("/health")).text
    assert "integrity check found" in banner and "/settings/integrity" in banner
    page = await admin.get("/settings/integrity")
    assert "bad_signature" in page.text


async def test_integrity_runs_are_rate_limited(admin):
    t = await admin.csrf()
    codes = []
    for _ in range(5):
        codes.append((await admin.b.post("/settings/integrity/run", data={"csrf_token": t})).status_code)
    assert codes[:3] == [200, 200, 200] and codes[-1] == 429


async def test_integrity_page_before_any_run(admin):
    page = await admin.get("/settings/integrity")
    assert "Not run since this service started" in page.text


# -- structure, headers, templates -----------------------------------------------------------------------
async def test_pages_have_csp_landmarks_labels_and_no_scripts(admin):
    await admin.change(T1, "set", "set", value="81")
    await admin.change(T2_SECRET, "set", "set", value=SECRETS[0])
    pages = [
        "/settings", "/settings?tier=T3", f"/settings/{T1}", f"/settings/{T2_SECRET}", f"/settings/{T3}",
        f"/settings/{T1}/history?restore=1", f"/settings/{T2_SECRET}/history", "/settings/integrity",
        "/settings/notifications", f"/settings/{T4}", f"/settings/{T5}",
    ]
    for path in pages:
        r = await admin.b.get(path)
        if r.status_code == 303:
            r = await admin.b.get(r.headers["location"])
        assert r.status_code == 200, path
        assert r.headers["content-security-policy"] == CONTENT_SECURITY_POLICY
        html = r.text
        assert not re.search(r"<script|<style|\sstyle=|\son\w+\s*=|(src|href|action)=[\"']?(https?:)?//", html, re.I), path
        s = Structure()
        s.feed(html)
        assert s.h1 == 1 and {"nav", "main", "header"} <= s.landmarks and s.skip, path
        assert all(i and i in s.label_for for i in s.inputs), path
        assert all(caption and header for caption, header in s.tables), path
        assert "SETTINGS_MASTER_KEY" in html


async def test_csp_on_redirects_and_errors(admin):
    t = await admin.csrf()
    samples = [
        await admin.b.post(f"/settings/{T1}/set", data={"csrf_token": t, "expected_version": "0"}),
        await admin.b.post(f"/settings/{T1}/set", data={"expected_version": "0"}),
        await admin.b.get("/settings/not-a-key"),
        await admin.b.get("/settings/NOPE/history"),
        await admin.b.post(f"/settings/{T1}/prepare", data={"csrf_token": t, "action": "zzz"}),
        await admin.b.get("/settings/%00"),
    ]
    assert {r.status_code for r in samples} >= {303, 403}
    for r in samples:
        assert r.headers["content-security-policy"] == CONTENT_SECURITY_POLICY


def test_templates_have_no_safe_filter_or_external_urls():
    templates = Path(admin_package.__file__).parent / "templates"
    for path in templates.glob("*.html"):
        body = path.read_text()
        assert "|safe" not in body.replace(" ", "") and "autoescape" not in body, path.name
        assert not re.search(r"(src|href|action)=[\"']?https?://", body), path.name
        body = re.sub(r'<script src="/static/[a-z0-9._-]+\.js" defer></script>', "", body)
        assert "<script" not in body and "style=" not in body, path.name


async def test_bad_filters_and_unknown_notice_codes_are_inert(admin):
    assert (await admin.b.get("/settings?section=zzz")).status_code == 400
    assert (await admin.b.get("/settings?tier=T9")).status_code == 400
    page = await admin.get(f"/settings/{T1}?notice=<script>alert(1)</script>")
    assert "alert(1)" not in page.text
    shown = await admin.get(f"/settings/{T1}?notice=done_set")
    assert "The setting was changed." in shown.text


# -- the sealed pending value -------------------------------------------------------------------------------
def test_pending_blob_is_bound_to_session_action_key_version_and_time(clock):
    key = b"k" * 32
    blob = sp.seal_pending(key, clock, "sess", "set", T1, 3, "very-secret-value")
    assert "very-secret-value" not in blob
    assert sp.open_pending(key, clock, "sess", "set", T1, 3, blob) == "very-secret-value"
    for args in (("other", "set", T1, 3), ("sess", "clear", T1, 3), ("sess", "set", "X", 3), ("sess", "set", T1, 4)):
        assert sp.is_missing(sp.open_pending(key, clock, *args, blob))
    assert sp.is_missing(sp.open_pending(b"j" * 32, clock, "sess", "set", T1, 3, blob))
    exp, nonce, sealed = blob.split(".")
    assert sp.is_missing(sp.open_pending(key, clock, "sess", "set", T1, 3, f"{int(exp) + 999}.{nonce}.{sealed}"))
    assert sp.is_missing(sp.open_pending(key, clock, "sess", "set", T1, 3, f"{exp}.{nonce}.{sealed[:-2]}AA"))
    for junk in (None, "", "a.b", "x.y.z", "1.2.3.4", "9" * 12000):
        assert sp.is_missing(sp.open_pending(key, clock, "sess", "set", T1, 3, junk))
    clock.advance(sp.PENDING_SECONDS)
    assert sp.is_missing(sp.open_pending(key, clock, "sess", "set", T1, 3, blob))
