"""The portal's read-only pages on real Postgres: gate, rendering, masking,
filters, audit paging, metrics, health and a structural accessibility check."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from backend.admin import cookies
from backend.admin.controllers.portal import build_registry
from backend.admin.gate.levels import LEVEL_ATTR, Level
from backend.admin.headers import CONTENT_SECURITY_POLICY
from backend.admin.services import audit
from backend.admin.services import pages as pg
from tests.admin.engines import fixture_engine
from tests.admin.conftest import needs_postgres
from tests.admin.portal_fixtures import ADMIN, OTHER_ADMIN, UA, Browser
from tests.admin.test_settings_store import ADMIN as ACTOR
from tests.admin.test_settings_store import PLANT, SECRET, T1, AUTH_ONLY, put

pytestmark = needs_postgres

IP = "127.0.0.1"
PAGES = ["/", "/health", "/config", "/metrics", "/audit", "/sessions", "/account"]
API = ["/api/audit"]


async def signed_in(portal, app, email=ADMIN, state="mfa_ok") -> Browser:
    token, _ = await portal.sessions.create(email, IP, UA, mfa_state=state)
    b = Browser(app)
    b.cookies[cookies.SESSION_COOKIE] = token
    return b


@pytest_asyncio.fixture(loop_scope="session")
async def superuser(server, migrated):
    engine = fixture_engine(server.url(migrated))
    yield engine
    await engine.dispose()


async def write_audit(engine, n=1, **kw):
    async with engine.begin() as conn:
        for i in range(n):
            await audit.write(
                conn, kw.get("action", "test.event"), "thing", str(i),
                kw.get("before"), kw.get("after"), kw.get("outcome", "success"),
                actor_kind="admin", actor_email=kw.get("actor", ADMIN), detail=kw.get("detail"),
            )


# -- gate ---------------------------------------------------------------------------
def page_routes():
    return [
        r for r in build_registry().router.routes
        if r.methods == {"GET"} and getattr(r.endpoint, LEVEL_ATTR, None) is Level.SECOND_FACTOR
        and "{" not in r.path
    ]


def test_every_second_factor_get_route_is_covered_here():
    paths = {r.path for r in page_routes()}
    assert set(PAGES + API) <= paths


def test_every_mutating_route_under_tasks_and_settings_declares_its_protection():
    from backend.admin.gate.stepup import STEPUP_REQUIRED_PREFIXES, undeclared_mutating_routes

    assert undeclared_mutating_routes(build_registry().router.routes, STEPUP_REQUIRED_PREFIXES) == []


@pytest.mark.parametrize("path", [r.path for r in page_routes()])
async def test_refused_below_second_factor_and_for_non_admins(portal, app, path):
    anon = Browser(app)
    half = await signed_in(portal, app, state="email_ok")
    stranger = await signed_in(portal, app, email="stranger@example.org")
    for b in (anon, half, stranger):
        response = await b.get(path)
        assert response.status_code in (303, 404, 401), (path, response.status_code)
        assert "<h1" not in response.text
        await b.aclose()


# -- rendering and structure ---------------------------------------------------------
class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.h1 = 0
        self.landmarks = set()
        self.ids, self.label_for, self.inputs = set(), set(), []
        self.tables = []  # [has_caption, has_col_th]
        self.skip = False
        self._table = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "h1":
            self.h1 += 1
        if tag in ("nav", "main", "header"):
            self.landmarks.add(tag)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "label" and a.get("for"):
            self.label_for.add(a["for"])
        if tag in ("input", "select") and a.get("type") != "hidden":
            self.inputs.append(a.get("id"))
        if tag == "a" and a.get("href") == "#main":
            self.skip = True
        if tag == "table":
            self._table = [False, False]
            self.tables.append(self._table)
        if tag == "caption" and self._table is not None:
            self._table[0] = True
        if tag == "th" and a.get("scope") == "col" and self._table is not None:
            self._table[1] = True


@pytest.mark.parametrize("path", PAGES)
async def test_page_renders_with_csp_and_accessible_structure(portal, app, path):
    b = await signed_in(portal, app)
    response = await b.get(path)
    assert response.status_code == 200
    assert response.headers["content-security-policy"] == CONTENT_SECURITY_POLICY
    assert "script-src 'self'" in CONTENT_SECURITY_POLICY and "style-src 'self'" in CONTENT_SECURITY_POLICY
    html = response.text
    assert not re.search(r"<script|<style|\sstyle=|\son\w+\s*=|(src|href|action)=[\"']?(https?:)?//", html, re.I)
    s = Structure()
    s.feed(html)
    assert s.h1 == 1 and {"nav", "main", "header"} <= s.landmarks and s.skip and "main" in s.ids
    assert all(i and i in s.label_for for i in s.inputs), "every input has a label"
    assert all(caption and header for caption, header in s.tables if path != "/metrics")
    assert "SETTINGS_MASTER_KEY" in html  # the permanent reminder
    assert 'aria-current="page"' in html or path == "/account" or path == "/"
    await b.aclose()


# -- secrets never reach a page ---------------------------------------------------------
async def test_secrets_never_appear_in_any_response(portal, app, runtime_engine, superuser, server):
    from backend.admin.services.settings_store import SettingsService, store_registry
    from tests.admin.test_settings_store import make_keys

    svc = SettingsService(runtime_engine, store_registry(), make_keys())
    secret_value = "Xq9-planted-" + PLANT
    await put(svc, SECRET, secret_value)
    await put(svc, AUTH_ONLY, secret_value + "-2")
    await put(svc, T1, 77)
    async with superuser.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO settings.service_state (service, instance, revision_applied, env_overrides) "
                "VALUES ('backend', 'b1', 1, ARRAY['MAIL_PASSWORD', :plant])"
            ),
            {"plant": PLANT},
        )
    await write_audit(
        runtime_engine, before={"password": PLANT, "note": "x"},
        after={"secret": "set", "token": PLANT, "value": PLANT[:6]}, detail={"api_key": PLANT},
    )
    b = await signed_in(portal, app)
    bodies = []
    for path in PAGES + API + ["/config?section=sso", "/config?tier=T3", "/audit?limit=200"]:
        r = await b.get(path)
        assert r.status_code == 200, path
        bodies.append(r.text)
    blob = "\n".join(bodies)
    assert PLANT not in blob and secret_value not in blob and "v2:" not in blob
    assert "planted-secret" not in blob
    # secrets: only set / not set; non-secrets: the value
    config = (await b.get("/config")).text
    row = re.search(rf"<code>{SECRET}</code>.*?</tr>", config, re.S).group(0)
    assert re.search(r"<td>\s*set\s*</td>", row) and "Xq9" not in row
    assert "<code>77</code>" in config
    auth_row = re.search(rf"<code>{AUTH_ONLY}</code>.*?</tr>", config, re.S).group(0)
    assert "overridden by environment" in auth_row
    await b.aclose()


def test_display_masking_is_applied_again():
    shown = pg._display_json({"password": PLANT, "nested": {"api_key": PLANT, "n": 1}})
    assert PLANT not in json.dumps(shown) and shown["nested"]["n"] == 1


def test_url_credentials_are_removed_from_shown_values():
    assert "hunter2" not in pg.shown_value("postgres://user:hunter2@db/x")
    assert pg.shown_value("a" * 500).endswith("...")


# -- configuration ---------------------------------------------------------------------
async def test_config_sources_t5_build_arguments_and_filters(portal, app, runtime_engine, superuser):
    b = await signed_in(portal, app)
    page = (await b.get("/config")).text
    assert "DATABASE_URL" in page and "environment only" in page
    assert "NEXT_PUBLIC_APP_URL" in page and "build argument" in page
    assert ADMIN in page and OTHER_ADMIN in page  # the super admin list
    only_t5 = (await b.get("/config?tier=T5")).text
    assert "AUTH_JWT_SECRET" not in only_t5 and "DATABASE_URL" in only_t5
    assert (await b.get("/config?section=zzz")).status_code == 400
    assert (await b.get("/config?tier=T9")).status_code == 400
    assert (await b.get("/config?section=" + "a" * 500)).status_code == 400
    async with superuser.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO settings.service_state (service, instance, revision_applied, restart_pending) "
                "VALUES ('backend', 'b1', 1, true)"
            )
        )
    from backend.admin.services.settings_store import SettingsService, store_registry
    from tests.admin.test_settings_store import make_keys

    svc = SettingsService(runtime_engine, store_registry(), make_keys())
    key = next(
        sp.key for sp in store_registry()
        if sp.tier.value == "T1" and not sp.is_secret and sp.reload_class.value == "R"
        and "backend" in sp.readers and sp.default is not None
    )
    await put(svc, key, store_registry().get(key).default)
    html = (await b.get("/config")).text
    assert "restart required" in html and "Restart required for changed settings" in html
    await b.aclose()


# -- audit -------------------------------------------------------------------------------
async def test_audit_keyset_paging_and_filters(portal, app, runtime_engine):
    await write_audit(runtime_engine, 4, action="alpha.one", actor="a@example.org")
    await write_audit(runtime_engine, 3, action="beta.two", actor="b@example.org", outcome="denied")
    b = await signed_in(portal, app)
    seen, before = [], None
    while True:
        url = "/api/audit?limit=3" + (f"&before={before}" if before else "")
        body = (await b.get(url)).json()
        assert len(body["items"]) <= 3
        seen += [i["seq"] for i in body["items"]]
        before = body["next_before"]
        if not before:
            break
    assert seen == sorted(seen, reverse=True) and len(seen) == len(set(seen)) >= 7
    head = (await b.get("/api/audit?limit=1")).json()["head"]
    assert head["seq"] == seen[0] and len(head["hash_prefix"]) == 16
    only = (await b.get("/api/audit?actor=B@example.org&outcome=denied")).json()["items"]
    assert len(only) == 3 and {i["action"] for i in only} == {"beta.two"}
    assert len((await b.get("/api/audit?action=alpha")).json()["items"]) == 4  # prefix, dot-separated
    assert len((await b.get("/api/audit?action=alp")).json()["items"]) == 0
    today = datetime.now(timezone.utc).date().isoformat()
    assert len((await b.get(f"/api/audit?action=alpha.one&from={today}&to={today}")).json()["items"]) == 4
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=2)).date().isoformat()
    assert (await b.get(f"/api/audit?action=alpha.one&from={tomorrow}")).json()["items"] == []
    page = await b.get("/audit?limit=2")
    assert 'rel="next"' in page.text and "before=" in page.text
    for bad in ("limit=0", "limit=201", "limit=x", "before=-1", "before=abc", "outcome=maybe",
                "from=yesterday", "to=2026-13-40", "action=A%20B", "actor=a%3Cb", "actor=" + "a" * 300):
        r = await b.get("/api/audit?" + bad)
        assert r.status_code == 400 and r.json()["error"] == "bad_filter", bad
        assert (await b.get("/audit?" + bad)).status_code == 400, bad
    await b.aclose()


async def test_audit_payloads_are_escaped(portal, app, runtime_engine):
    await write_audit(runtime_engine, before={"note": "<script>alert(1)</script>"}, actor="x@example.org")
    b = await signed_in(portal, app)
    html = (await b.get("/audit")).text
    assert "<script>alert(1)" not in html and "&lt;script&gt;alert(1)" in html
    await b.aclose()


# -- sessions ------------------------------------------------------------------------------
async def test_sessions_page_marks_current_and_posts_with_csrf(portal, app):
    b = await signed_in(portal, app)
    await portal.sessions.create(ADMIN, "127.0.0.2", UA, mfa_state="mfa_ok")
    html = (await b.get("/sessions")).text
    assert "This session" in html and len(re.findall(r"sessions/[0-9a-f-]+/revoke", html)) == 1 and "127.0.0.2" in html
    token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
    target = re.search(r'action="(/account/sessions/[0-9a-f-]+/revoke)"', html).group(1)
    assert (await b.post(target, data={"csrf_token": token})).status_code == 303
    assert not re.search(r"sessions/[0-9a-f-]+/revoke", (await b.get("/sessions")).text)
    await b.aclose()


# -- health ---------------------------------------------------------------------------------
async def test_health_shows_heartbeats_stopped_and_unavailable_schemas(portal, app, superuser):
    async with superuser.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO settings.service_state (service, instance, reported_at, revision_applied, rejected_keys) "
                "VALUES ('backend', 'fresh', now(), 0, ARRAY['A_KEY']), "
                "('auth', 'old', now() - interval '1 hour', 0, '{}')"
            )
        )
    b = await signed_in(portal, app)
    html = (await b.get("/health")).text
    row = lambda name, extra="": re.search(rf"<th scope=\"row\">{name}</th>\s*{extra}.*?</tr>", html, re.S).group(0)
    assert "reporting" in row("backend", "<td>fresh</td>") and "stopped" in row("auth", "<td>old</td>")
    assert "current" in row("admin")
    assert html.count("not available to this role") == 3
    assert "Reachable" in html
    await b.aclose()


# -- metrics ---------------------------------------------------------------------------------
async def test_metrics_page_without_application_tables_says_unavailable(portal, app):
    b = await signed_in(portal, app)
    html = (await b.get("/metrics")).text
    assert "not available" in html
    await b.aclose()


async def test_platform_counts_match_a_seeded_database(server, migrated, portal, app, superuser):
    from backend.db.startup import MIGRATIONS as APP
    from common.db.ddl import helper_function_ddl
    from common.db.schema_guard import upgrade_schema
    from tests.admin.conftest import roles_sql
    from tests.app.db.test_auto_migrate import _execute
    from bson import ObjectId

    await upgrade_schema(server.url(migrated), APP)
    async with superuser.begin() as conn:  # the auth package is not installed here: its users table, as the auth migration lays it out
        for statement in helper_function_ddl("auth"):
            await conn.execute(text(statement))
        await conn.execute(text(
            "CREATE TABLE auth.users (id text PRIMARY KEY, doc jsonb NOT NULL, "
            "plan text GENERATED ALWAYS AS (auth.bc_text(doc -> 'plan')) STORED)"))
    # the roles script runs on every deploy: it grants the counts function's owner
    # SELECT on the tables that exist by now
    await _execute(
        server.url(migrated),
        roles_sql(server.suffix, server.admin_pw, server.mig_pw, server.tasks_pw),
    )
    now = datetime.now(timezone.utc)

    def oid(days_ago: float) -> str:
        return str(ObjectId.from_datetime(now - timedelta(days=days_ago)))

    async with superuser.begin() as conn:
        for i, (days, doc) in enumerate([(100, {}), (10, {"disabled": True}), (1, {})]):
            await conn.execute(text("INSERT INTO app.workspaces (id, doc, _bc_checksum) VALUES (:i, CAST(:d AS jsonb), 'x')"),
                               {"i": oid(days), "d": json.dumps({"workspace_name": f"w{i}", **doc})})
        forms = [(50, "f1", "u1", "self"), (5, "f2", "u1", "weird<b>x"), (2, "f3", "u2", None)]
        for days, form, user, provider in forms:
            settings = {"provider": provider} if provider else {}
            await conn.execute(text("INSERT INTO app.workspace_forms (id, doc, _bc_checksum) VALUES (:i, CAST(:d AS jsonb), 'x')"),
                               {"i": oid(days), "d": json.dumps({"form_id": form, "user_id": user, "workspace_id": "w", "settings": settings})})
        await conn.execute(text("INSERT INTO app.form_versions (id, doc, _bc_checksum) VALUES (:i, CAST(:d AS jsonb), 'x')"),
                           {"i": oid(1), "d": json.dumps({"form_id": "f1", "version": 1})})
        iso = lambda d: (now - timedelta(days=d)).strftime("%Y-%m-%dT%H:%M:%S")
        for n, (days, owner, answers) in enumerate([(1, "o1@x", True), (3, "o1@x", True), (20, "", True), (40, "o2@x", True), (2, "o3@x", False)]):
            doc = {"form_id": "f1", "dataOwnerIdentifier": owner, "created_at": iso(days)}
            if answers:
                doc["answers"] = {}
            await conn.execute(
                text("INSERT INTO app.form_responses (id, doc, created_at, _bc_checksum) VALUES (:i, CAST(:d AS jsonb), :c, 'x')"),
                {"i": oid(days), "d": json.dumps(doc), "c": now - timedelta(days=days)},
            )
        for days, plan, seen in [(200, "PRO", 2), (3, None, 400)]:
            doc = {"email": f"u{days}@x", "last_logged_in": {"$date": (now - timedelta(days=seen)).strftime("%Y-%m-%dT%H:%M:%SZ")}}
            if plan:
                doc["plan"] = plan
            await conn.execute(text("INSERT INTO auth.users (id, doc) VALUES (:i, CAST(:d AS jsonb))"),
                               {"i": oid(days), "d": json.dumps(doc)})

        # malformed last_logged_in values count as inactive and never break the page
        for days, value in [(300, {"$date": "not a date"}), (301, "2026-13-45T99:00:00Z")]:
            await conn.execute(text("INSERT INTO auth.users (id, doc) VALUES (:i, CAST(:d AS jsonb))"),
                               {"i": oid(days), "d": json.dumps({"email": f"bad{days}@x", "last_logged_in": value})})

    b = await signed_in(portal, app)
    counts, why = await portal.pages.metrics()
    assert why is None, why
    assert counts["organizations"] == {"total": 3, "new_last_30_days": 2, "disabled": 1}
    assert counts["forms"]["total"] == 3 and counts["forms"]["published"] == 1
    assert counts["forms"]["by_provider"] == {"self": 1, "other": 1, "unknown": 1}
    assert counts["forms"]["new_last_30_days"] == 2
    assert counts["form_creators"] == {"total": 2, "active_last_30_days": 2}
    assert counts["responses"] == {"total": 4, "last_7_days": 2, "last_30_days": 3}
    assert counts["form_responders"] == {"identified": 2, "identified_responses": 3, "anonymous_responses": 1}
    assert (counts["form_responders"]["identified_responses"] + counts["form_responders"]["anonymous_responses"]
            == counts["responses"]["total"])
    assert counts["users"]["total"] == 4 and counts["users"]["new_last_30_days"] == 1
    assert counts["users"]["active_last_30_days"] == 1
    assert counts["users"]["by_plan"] == {"FREE": 3, "PRO": 1}
    assert len(counts["weekly"]) == 12 and sum(w["responses"] for w in counts["weekly"]) == 4
    html = (await b.get("/metrics")).text
    assert "Platform counts are not available" not in html and "self" in html
    # one definer function per owning schema, each owned by a role that cannot log in,
    # creates nothing, owns no table and reads only its own schema (the hostile-owner
    # proofs are in test_db_privilege_model.py)
    async with superuser.connect() as conn:
        for fn, owner_role, own, other in (
            ("platform_counts_app", f"bc_count_app_{server.suffix}", "app", "auth"),
            ("platform_counts_auth", f"bc_count_auth_{server.suffix}", "auth", "app"),
        ):
            owner = (await conn.execute(text(
                "SELECT r.rolname, r.rolsuper, r.rolcanlogin, r.rolcreaterole, r.rolcreatedb, r.rolbypassrls "
                "FROM pg_proc p JOIN pg_roles r ON r.oid = p.proowner WHERE p.proname = :f"), {"f": fn})).one()
            assert owner.rolname == owner_role
            assert not (owner.rolsuper or owner.rolcanlogin or owner.rolcreaterole or owner.rolcreatedb or owner.rolbypassrls)
            creates = (await conn.execute(text(
                "SELECT nspname FROM pg_namespace WHERE has_schema_privilege(:r, oid, 'CREATE')"),
                {"r": owner.rolname})).all()
            assert creates == []
            owned = (await conn.execute(text(
                "SELECT count(*) FROM pg_class c WHERE c.relowner = (SELECT oid FROM pg_roles WHERE rolname = :r)"),
                {"r": owner.rolname})).scalar_one()
            assert owned == 0
            definition = (await conn.execute(text(
                "SELECT pg_get_functiondef(p.oid) FROM pg_proc p WHERE p.proname = :f"), {"f": fn})).scalar_one()
            config = (await conn.execute(text(
                "SELECT proconfig FROM pg_proc WHERE proname = :f"), {"f": fn})).scalar_one()
            assert "search_path=pg_catalog, pg_temp" in config
            assert "SECURITY DEFINER" in definition
            body = definition.split("$function$")[1]
            # no schema-qualified function call (tables are qualified, calls never are)
            assert not re.search(r"[A-Za-z_]+\.[A-Za-z_]+\s*\(", body), definition
            # reads its own schema's tables and no other's
            assert f"{other}." not in body.replace("jsonb_", "")
        # the old cross-schema function and its owner role are gone
        assert (await conn.execute(text("SELECT count(*) FROM pg_proc WHERE proname = 'platform_counts'"))).scalar_one() == 0
        assert (await conn.execute(text(
            "SELECT count(*) FROM pg_roles WHERE rolname = :r"), {"r": f"bc_admin_counts_{server.suffix}"})).scalar_one() == 0
        await conn.execute(text("DROP FUNCTION auth.bc_ts(jsonb)"))
        await conn.commit()
    for role in ("auth", "app"):
        hostile = create_async_engine(server.url(migrated, f"reader:{role}"), poolclass=NullPool)
        try:
            if role == "auth":
                async with hostile.begin() as conn:
                    await conn.execute(text(
                        "CREATE FUNCTION auth.bc_ts(v jsonb) RETURNS timestamptz LANGUAGE plpgsql AS "
                        "$$ BEGIN RAISE EXCEPTION 'ran as the owner'; END $$"))
            for statement in (
                "ALTER FUNCTION admin.platform_counts_app() OWNER TO CURRENT_USER",
                "CREATE OR REPLACE FUNCTION admin.platform_counts_auth() RETURNS jsonb LANGUAGE sql AS $$ SELECT '{}'::jsonb $$",
                "SELECT admin.platform_counts_app()",
                "SELECT admin.platform_counts_auth()",
            ):
                with pytest.raises(Exception):
                    async with hostile.begin() as conn:
                        await conn.execute(text(statement))
        finally:
            await hostile.dispose()
    portal.pages._metrics = None
    again, why = await portal.pages.metrics()
    assert why is None and again["users"] == counts["users"] and again["organizations"] == counts["organizations"]
    # the app and auth schemas stay out of the admin role's reach
    async with portal.engine.connect() as conn:
        with pytest.raises(Exception):
            await conn.execute(text("SELECT count(*) FROM app.workspaces"))
    await b.aclose()


async def test_only_the_admin_role_may_run_the_counts_function(server, migrated):
    for logical in ("app", "auth", "google", "tasks"):
        engine = create_async_engine(server.url(migrated, f"reader:{logical}"), poolclass=NullPool)
        try:
            async with engine.connect() as conn:
                with pytest.raises(Exception):
                    await conn.execute(text("SELECT admin.platform_counts_app()"))
                with pytest.raises(Exception):
                    await conn.execute(text("SELECT admin.platform_counts_auth()"))
        finally:
            await engine.dispose()


async def test_audit_date_bounds_that_overflow_are_a_bad_filter_not_an_error(portal, app):
    b = await signed_in(portal, app)
    for name in ("to", "from"):
        for value in ("9999-12-31", "0001-01-01", "9999-12-31T23:59:59"):
            r = await b.get(f"/api/audit?{name}={value}")
            assert r.status_code in (200, 400), (name, value, r.status_code)
    assert (await b.get("/api/audit?to=9999-12-31")).status_code == 400
    assert (await b.get("/audit?to=9999-12-31")).status_code == 400
    await b.aclose()


def test_url_settings_show_only_their_origin():
    hook = "https://hooks.example.com:8443/services/T000/B000/SECRETTOKEN?x=1"
    shown = pg.shown_value(hook, True)
    assert shown == "https://hooks.example.com:8443/[path hidden]"
    assert pg.shown_value("https://user:pw@hooks.example.com/", True) == "https://hooks.example.com"
    assert pg.shown_value("not a url", True) == "[hidden]"
    spec = next(sp for sp in pg.all_specs() if sp.key == "EVENT_WEBHOOK_URL")
    row = pg.PageService._config_row(spec, None, set(), [])
    assert row.value is None or "SECRET" not in row.value


def test_provider_names_are_an_allowlist_with_an_other_bucket():
    shown = pg._known_providers({"google": 2, "self": 1, "x<script>": 3, "y": 4, "unknown": 5})
    assert shown == {"google": 2, "self": 1, "other": 7, "unknown": 5}
