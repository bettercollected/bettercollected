"""Gate levels 2-4, route reachability by session state, CSRF and response headers."""

from __future__ import annotations

import re
import uuid

import pytest

from backend.admin import cookies
from backend.admin.asgi import get_admin_application
from backend.admin.controllers.portal import build_registry
from backend.admin.gate.levels import Level, RouteRegistry
from backend.admin.gate.settings import GateSettings
from backend.admin.headers import CONTENT_SECURITY_POLICY
from backend.admin.security import csrf
from tests.admin.conftest import needs_postgres
from tests.admin.portal_fixtures import ADMIN, ORIGIN, UA, Browser, sign_in

ROUTES = [
    r for r in build_registry().router.routes
]


def fill(path: str) -> str:
    return path.replace("{name}", "admin.css").replace("{session_id}", str(uuid.uuid4()))


def level_of(route) -> Level:
    return route.endpoint.admin_level


# -- gate order, no database ----------------------------------------------------


async def test_levels_run_in_order_and_denials_are_401_or_303():
    seen = []

    def checker(level, ok=True, reason=None):
        async def check(scope):
            seen.append(level)
            if not ok:
                scope["state"]["deny_reason"] = reason
            return ok

        return check

    reg = RouteRegistry()

    @reg.route("/page", level=Level.SECOND_FACTOR)
    async def page():
        return {"ok": True}

    @reg.route("/api/thing", level=Level.SECOND_FACTOR)
    async def thing():
        return {"ok": True}

    def build(fails=None):
        fails = fails or {}
        checkers = {
            lvl: checker(lvl, ok=lvl not in fails, reason=fails.get(lvl))
            for lvl in (Level.SESSION, Level.ADMIN, Level.SECOND_FACTOR)
        }
        return get_admin_application(GateSettings.from_env({}), checkers, reg)

    async def call(app, path):
        from tests.admin.test_gate import call as gate_call

        return await gate_call(app, path=path)

    ok = await call(build(), "/page")
    assert ok[0] == 200 and seen == [Level.SESSION, Level.ADMIN, Level.SECOND_FACTOR]
    seen.clear()
    denied = await call(build({Level.ADMIN: "x"}), "/page")
    assert denied[0] == 303 and seen == [Level.SESSION, Level.ADMIN]  # stops at the failure
    assert denied[1]["location"] == "/login"
    seen.clear()
    api = await call(build({Level.SESSION: "x"}), "/api/thing")
    assert api[0] == 401 and seen == [Level.SESSION] and b"unauthenticated" in api[2]
    seen.clear()
    mfa = await call(build({Level.SECOND_FACTOR: "mfa_required"}), "/page")
    assert mfa[0] == 303 and mfa[1]["location"] == "/mfa"


# -- reachability by session state ----------------------------------------------


@needs_postgres
@pytest.mark.parametrize("route", ROUTES, ids=lambda r: f"{sorted(r.methods)[0]} {r.path}")
async def test_email_ok_session_reaches_only_mfa_logout_and_static(
    route, app, portal, transport
):
    level = level_of(route)
    if route.path == "/logout" or level == Level.ADDRESS and not route.path.startswith("/static"):
        pytest.skip("covered by dedicated tests")
    b = Browser(app)
    await sign_in(b, transport)
    session = (await portal.sessions.list_live(ADMIN))[0]
    token = csrf.session_token(portal.csrf_key, str(session.id))
    method = sorted(route.methods)[0]
    kw = {"headers": {"x-csrf-token": token}}
    if route.path.startswith("/api/") and method == "POST":
        kw["json"] = {}
    response = await b.request(method, fill(route.path), **kw)
    reachable = level <= Level.ADMIN
    if reachable and route.path.startswith("/mfa"):
        # narrowed by state: no factor yet -> only /mfa/enrol*, others redirect there
        assert response.status_code in (200, 303), route.path
        if response.status_code == 303:
            assert response.headers["location"].startswith("/mfa"), route.path
    elif reachable:
        assert response.status_code == 200, route.path
    elif route.path.startswith("/api/"):
        assert response.status_code == 401
    else:
        assert response.status_code == 303 and response.headers["location"] == "/mfa"
    await b.aclose()


@needs_postgres
async def test_mfa_ok_session_reaches_the_shell_and_api(app, portal):
    token, session = await portal.sessions.create(ADMIN, "127.0.0.1", UA, mfa_state="mfa_ok")
    b = Browser(app)
    b.cookies[cookies.SESSION_COOKIE] = token
    assert (await b.get("/")).status_code == 200
    me = await b.get("/api/me")
    assert me.json() == {"email": ADMIN, "mfa_state": "mfa_ok"}
    assert (await b.get("/mfa")).headers["location"] == "/"
    assert len((await b.get("/api/sessions")).json()) == 1
    await b.aclose()


@needs_postgres
async def test_unauthenticated_requests(app):
    b = Browser(app)
    page = await b.get("/mfa")
    api = await b.get("/api/me")
    assert page.status_code == 303 and page.headers["location"] == "/login"
    assert api.status_code == 401 and api.json() == {"error": "unauthenticated"}
    await b.aclose()


# -- CSRF -------------------------------------------------------------------------


async def logged_in(app, portal, state="mfa_ok"):
    token, session = await portal.sessions.create(ADMIN, "127.0.0.1", UA, mfa_state=state)
    b = Browser(app)
    b.cookies[cookies.SESSION_COOKIE] = token
    return b, csrf.session_token(portal.csrf_key, str(session.id)), session


@needs_postgres
async def test_session_csrf_token_required_for_post(app, portal):
    b, token, session = await logged_in(app, portal)
    path = "/api/sessions/revoke-others"
    assert (await b.post(path, json={})).status_code == 403
    assert (await b.post(path, json={}, headers={"x-csrf-token": "wrong"})).status_code == 403
    assert (await b.post(path, json={}, headers={"x-csrf-token": token + "x"})).status_code == 403
    ok = await b.post(path, json={}, headers={"x-csrf-token": token})
    assert ok.status_code == 200 and ok.json() == {"revoked": 0}
    await b.aclose()


@needs_postgres
async def test_token_of_another_session_is_refused(app, portal):
    b, _, _ = await logged_in(app, portal)
    _, other, _ = await logged_in(app, portal)
    r = await b.post("/api/sessions/revoke-others", json={}, headers={"x-csrf-token": other})
    assert r.status_code == 403
    await b.aclose()


@needs_postgres
@pytest.mark.parametrize(
    "origin,extra",
    [
        ("https://evil.example", {}),
        ("http://localhost:8100", {}),  # wrong scheme
        ("https://localhost:9999", {}),  # wrong port
        ("null", {}),
        (None, {}),  # neither Origin nor Referer
        (ORIGIN, {"sec-fetch-site": "cross-site"}),
        (ORIGIN, {"sec-fetch-site": "same-site"}),
    ],
)
async def test_state_changing_requests_check_origin(app, portal, origin, extra):
    b, token, _ = await logged_in(app, portal)
    headers = {"x-csrf-token": token, **extra}
    r = await b.post("/api/sessions/revoke-others", json={}, origin=origin, headers=headers)
    assert r.status_code == 403
    await b.aclose()


@needs_postgres
async def test_referer_is_the_fallback_and_same_origin_passes(app, portal):
    b, token, _ = await logged_in(app, portal)
    headers = {"x-csrf-token": token, "referer": ORIGIN + "/", "sec-fetch-site": "same-origin"}
    r = await b.post("/api/sessions/revoke-others", json={}, origin=None, headers=headers)
    assert r.status_code == 200
    await b.aclose()


@needs_postgres
async def test_json_endpoints_reject_forms(app, portal):
    b, token, _ = await logged_in(app, portal)
    r = await b.post(
        "/api/sessions/revoke-others", data={"csrf_token": token}, headers={}
    )
    assert r.status_code == 415
    await b.aclose()


@needs_postgres
async def test_form_field_token_works_for_page_posts(app, portal):
    b, token, _ = await logged_in(app, portal, state="email_ok")
    assert (await b.post("/logout", data={"csrf_token": "bad"})).status_code == 403
    r = await b.post("/logout", data={"csrf_token": token})
    assert r.status_code == 303
    await b.aclose()


@needs_postgres
async def test_pre_login_forms_use_double_submit(app):
    b = Browser(app)
    token = await b.form_token("/login")
    good = {"email": ADMIN, "csrf_token": token}
    assert (await b.post("/login", data={"email": ADMIN})).status_code == 403
    assert (await b.post("/login", data={**good, "csrf_token": "x"})).status_code == 403
    assert (await b.post("/login", data=good, origin="https://evil.example")).status_code == 403
    assert (
        await b.post("/login", data=good, headers={"sec-fetch-site": "cross-site"})
    ).status_code == 403
    no_cookie = Browser(app)  # token without the matching cookie
    assert (await no_cookie.post("/login", data=good)).status_code == 403
    assert (await b.post("/login", data=good)).status_code == 303
    line = next(l for l in b.set_cookie_lines if l.startswith("__Host-bcadmin-csrf="))
    assert "secure" in line.lower() and "httponly" in line.lower()
    await b.aclose()
    await no_cookie.aclose()


@needs_postgres
async def test_get_never_changes_state(app, portal, runtime_engine):
    b, _, _ = await logged_in(app, portal)
    before = len(await portal.sessions.list_live(ADMIN))
    for path in ("/", "/api/me", "/api/sessions", "/logout", "/login", "/mfa"):
        await b.get(path)
    assert len(await portal.sessions.list_live(ADMIN)) == before
    await b.aclose()


# -- headers, static files ---------------------------------------------------------


@needs_postgres
async def test_every_response_carries_the_security_headers(app, portal):
    b, token, _ = await logged_in(app, portal)
    anon = Browser(app)
    responses = [
        await b.get("/"),
        await b.get("/nothing-here"),  # 404
        await b.post("/api/sessions/revoke-others", json={}),  # 403
        await anon.get("/api/me"),  # 401
        await anon.get("/mfa"),  # 303
        await anon.get("/login"),
        await anon.get("/static/admin.css"),
        await anon.post("/login", data={"email": "x"}),  # 403
    ]
    assert {r.status_code for r in responses} >= {200, 303, 401, 403, 404}
    for r in responses:
        assert r.headers["content-security-policy"] == CONTENT_SECURITY_POLICY
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["referrer-policy"] == "no-referrer"
        assert r.headers["cache-control"] == "no-store"
        assert "access-control-allow-origin" not in r.headers
    await b.aclose()
    await anon.aclose()


@needs_postgres
async def test_static_serves_the_stylesheet_only(app):
    b = Browser(app)
    css = await b.get("/static/admin.css")
    assert css.status_code == 200 and css.headers["content-type"].startswith("text/css")
    for path in ("/static/", "/static", "/static/..%2Fasgi.py", "/static/asgi.py",
                 "/static/missing.css", "/static/.css", "/static/%2e%2e/config.py"):
        assert (await b.get(path)).status_code == 404, path
    await b.aclose()


@needs_postgres
async def test_pages_have_no_inline_script_or_style(app):
    b = Browser(app)
    for path in ("/login", "/login/code"):
        html = (await b.get(path)).text
        assert not re.search(r"<script|<style|\sstyle=|\son\w+=", html, re.I)
        assert 'autocomplete' in html and "<label" in html and "skip-link" in html
    assert 'autocomplete="one-time-code"' in (await b.get("/login/code")).text
    await b.aclose()
