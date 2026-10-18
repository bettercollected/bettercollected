"""The portal's task pages on real Postgres: gate, forms, the prepare/confirm
step-up, signed requests the real runner accepts, cancel, resume, audit, escaping
and structure."""

from __future__ import annotations

import json
import re
import uuid
from datetime import timedelta
from html.parser import HTMLParser

import pytest
import pytest_asyncio
from sqlalchemy import text

from backend.admin import cookies
from backend.admin.controllers.portal import build_registry
from backend.admin.controllers.tasks import APPLY_ACTION, apply_binding
from backend.admin.gate.levels import LEVEL_ATTR, Level
from backend.admin.gate.stepup import STEPUP_ATTR, ActionBound
from backend.admin.services import audit, taskform
from backend.admin.services.stepup import action_hash
from backend.admin.tasks import catalog, signing
from backend.admin.tasks.catalog import responses_backfill, responses_check, selftest, selftest_slow
from backend.admin.tasks.impl import build_registry as build_task_registry
from backend.admin.tasks.runner.runner import Runner
from tests.admin.conftest import needs_postgres
from tests.admin.portal_fixtures import ADMIN, UA, Browser
from tests.admin.test_portal_mfa import csrf_of, enrol_direct

pytestmark = needs_postgres

IP = "127.0.0.1"
TOKEN_FIELD = re.compile(r'name="stepup_token" value="([^"]+)"')
SLOW = "selftest_slow"
GUARDED = "selftest_guarded"
RUN_ID = str(uuid.uuid4())


# -- helpers ----------------------------------------------------------------------------
class Ctx:
    def __init__(self, portal, app, clock, browser, session, secret, codes, owner, tasks_engine):
        self.portal, self.app, self.clock, self.b = portal, app, clock, browser
        self.session, self.secret, self.codes = session, secret, list(codes)
        self.owner, self.tasks_engine = owner, tasks_engine

    @property
    def csrf(self) -> str:
        return csrf_of(self.portal, self.session)

    def code(self) -> str:
        return self.codes.pop()

    async def post(self, path, data=None, **kw):
        return await self.b.post(path, data={"csrf_token": self.csrf, **(data or {})}, **kw)

    async def prepare(self, action, data):
        return await self.post("/tasks/prepare", {"action": action, "code": self.code(), **data})

    async def apply(self, task, fields=None, expect=200):
        """The full no-JavaScript flow: prepare with a code, then confirm."""
        fields = {f"p_{k}": v for k, v in (fields or {}).items()}
        prepared = await self.prepare("apply", {"task": task, **fields})
        assert prepared.status_code == expect, prepared.text[:300]
        token = TOKEN_FIELD.search(prepared.text)
        if not token:
            return prepared, None
        form = dict(re.findall(r'<input type="hidden" name="(p_[a-z_]+)" value="([^"]*)"', prepared.text))
        final = await self.post(f"/tasks/{task}/apply", {"stepup_token": token.group(1), **form})
        return prepared, final

    def runner(self) -> Runner:
        return Runner(self.tasks_engine, build_task_registry(), clock=self.clock, heartbeat_seconds=None)

    async def drain(self) -> int:
        runner, n = self.runner(), 0
        while await runner.run_once():
            n += 1
        return n

    async def sql(self, query, **params):
        async with self.owner.connect() as conn:
            return (await conn.execute(text(query), params)).mappings().all()

    async def runs(self, task=None):
        rows = await self.sql("SELECT * FROM tasks.runs ORDER BY created_at, id")
        return [r for r in rows if task is None or r["task"] == task]

    async def audit_rows(self, action):
        return await self.sql("SELECT * FROM admin.audit_log WHERE action = :a ORDER BY seq", a=action)

    async def dry_run(self, task, fields=None):
        response = await self.post(
            f"/tasks/{task}/dry-run", {f"p_{k}": v for k, v in (fields or {}).items()}
        )
        assert response.status_code == 303, response.text[:300]
        return response.headers["location"].split("?")[0].rsplit("/", 1)[1]


@pytest_asyncio.fixture(loop_scope="session")
async def ctx(portal, app, clock, monkeypatch, tasks_engine, owner_engine):
    monkeypatch.setenv("ADMIN_TASKS_SELFTEST", "1")
    secret, codes, token, session = await enrol_direct(portal, clock)
    b = Browser(app)
    b.cookies[cookies.SESSION_COOKIE] = token
    yield Ctx(portal, app, clock, b, session, secret, codes, owner_engine, tasks_engine)
    await b.aclose()


# -- gate -----------------------------------------------------------------------------------
def task_routes():
    out = []
    for r in build_registry().router.routes:
        if r.path.startswith(("/tasks", "/api/tasks")):
            for method in sorted(r.methods):
                out.append((method, r.path))
    return out


def concrete(path: str) -> str:
    return path.replace("{name}", "selftest").replace("{run_id}", RUN_ID)


def test_every_task_route_is_second_factor_and_mutating_ones_are_guarded():
    routes = [r for r in build_registry().router.routes if r.path.startswith(("/tasks", "/api/tasks"))]
    assert len(routes) >= 10
    for r in routes:
        assert getattr(r.endpoint, LEVEL_ATTR) is Level.SECOND_FACTOR, r.path
        if r.methods != {"GET"}:
            guarded = getattr(r.endpoint, STEPUP_ATTR, None) or getattr(r.endpoint, "admin_stepup_exempt", None)
            assert guarded, r.path
    bound = {r.path: getattr(r.endpoint, STEPUP_ATTR) for r in routes if isinstance(getattr(r.endpoint, STEPUP_ATTR, None), ActionBound)}
    assert set(bound) == {"/tasks/{name}/apply", "/tasks/runs/{run_id}/cancel", "/tasks/runs/{run_id}/resume"}


@pytest.mark.parametrize("method,path", task_routes())
async def test_refused_below_second_factor_and_for_non_admins(portal, app, method, path):
    sessions = []
    for email, state in ((ADMIN, "email_ok"), ("stranger@example.org", "mfa_ok")):
        token, _ = await portal.sessions.create(email, IP, UA, mfa_state=state)
        b = Browser(app)
        b.cookies[cookies.SESSION_COOKIE] = token
        sessions.append(b)
    for b in (Browser(app), *sessions):
        response = await b.request(method, concrete(path), data={"csrf_token": "x"} if method == "POST" else None)
        assert response.status_code in (303, 401, 403, 404), (path, response.status_code)
        assert "<h1" not in response.text
        await b.aclose()


async def test_mutating_routes_need_csrf_and_a_valid_action_bound_token(ctx):
    selftest_task = SLOW
    bare = {"p_items": "10"}
    # no CSRF token: refused before anything else
    for path in (f"/tasks/{selftest_task}/dry-run", f"/tasks/{selftest_task}/apply", "/tasks/prepare",
                 f"/tasks/runs/{RUN_ID}/cancel", f"/tasks/runs/{RUN_ID}/resume"):
        assert (await ctx.b.post(path, data=bare)).status_code == 403, path
    # no / junk step-up token on the bound routes
    for path in (f"/tasks/{selftest_task}/apply", f"/tasks/runs/{RUN_ID}/cancel", f"/tasks/runs/{RUN_ID}/resume"):
        assert (await ctx.post(path, bare)).status_code == 403, path
        assert (await ctx.post(path, {**bare, "stepup_token": "junk"})).status_code == 403, path
    assert await ctx.runs() == []
    assert await ctx.audit_rows("task.run.requested") == []


async def test_a_token_bound_to_other_params_or_another_run_is_refused_and_tokens_are_single_use(ctx):
    meta = selftest_slow.META
    good = {"items": 10, "batch_size": 5, "emit_events": 0, "fail_at": -1, "decline": False, "write_probe": False}

    def issue(params):
        return ctx.portal.stepup.issue(ctx.session, action_hash(APPLY_ACTION, *apply_binding(meta, params)))

    fields = {"stepup_token": None, "p_items": "10", "p_batch_size": "5", "p_emit_events": "0", "p_fail_at": "-1"}
    # token for items=11 used with items=10
    tok = issue({**good, "items": 11})
    assert (await ctx.post(f"/tasks/{SLOW}/apply", {**fields, "stepup_token": tok})).status_code == 403
    # token for another task name
    other = ctx.portal.stepup.issue(ctx.session, action_hash(APPLY_ACTION, *apply_binding(selftest_slow.GUARDED_META, good)))
    assert (await ctx.post(f"/tasks/{SLOW}/apply", {**fields, "stepup_token": other})).status_code == 403
    # a cancel token cannot start a run, nor an apply token cancel a run
    cancel_tok = ctx.portal.stepup.issue(ctx.session, action_hash("tasks.cancel", RUN_ID))
    assert (await ctx.post(f"/tasks/{SLOW}/apply", {**fields, "stepup_token": cancel_tok})).status_code == 403
    assert (await ctx.post(f"/tasks/runs/{RUN_ID}/cancel", {"stepup_token": issue(good)})).status_code == 403
    # the right token works once, then never again
    tok = issue(good)
    first = await ctx.post(f"/tasks/{SLOW}/apply", {**fields, "stepup_token": tok})
    assert first.status_code == 303, first.text[:200]
    replay = await ctx.post(f"/tasks/{SLOW}/apply", {**fields, "stepup_token": tok})
    assert replay.status_code == 403
    assert len(await ctx.runs(SLOW)) == 1
    # an expired token
    stale = issue(good)
    ctx.clock.advance(200)
    assert (await ctx.post(f"/tasks/{SLOW}/apply", {**fields, "stepup_token": stale})).status_code == 403


# -- list and forms ---------------------------------------------------------------------------
async def test_task_list_shows_catalog_and_latest_run(ctx):
    html = (await ctx.b.get("/tasks")).text
    for meta in catalog.all_meta():
        assert meta.name in html
    assert 'aria-current="page">Tasks' in html and "never run" in html
    run_id = await ctx.dry_run("selftest", {"rounds": "2"})
    html = (await ctx.b.get("/tasks")).text
    assert f"/tasks/runs/{run_id}" in html and "queued" in html


async def test_unknown_task_is_404(ctx):
    assert (await ctx.b.get("/tasks/nope")).status_code == 404
    assert (await ctx.post("/tasks/nope/dry-run", {})).status_code == 404
    assert (await ctx.post("/tasks/prepare", {"action": "apply", "task": "nope", "code": "x"})).status_code == 404


async def test_backfill_form_renders_typed_fields(ctx):
    html = (await ctx.b.get("/tasks/responses.backfill_workspaces")).text
    assert '<select id="p_stores"' in html and all(f'value="{v}"' in html for v in ("auto", "mongo", "postgres", "both"))
    assert re.search(r'<input type="number" id="p_batch_size"[^>]*min="100"[^>]*max="1000"', html)
    assert 'value="500"' in html
    assert re.search(r'<input type="text" id="p_workspace_id"[^>]*pattern="\^\[A-Za-z0-9\]', html)
    assert re.search(r'<textarea id="p_form_ids"[^>]*>', html) and "at most 100" in html
    assert "same parameters" in html and "Dry run" in html and "Apply..." in html
    # the read-only task has one button and no apply
    check = (await ctx.b.get("/tasks/responses.check_undecryptable")).text
    assert ">Run</button>" in check and "Apply..." not in check


def test_form_fields_cover_every_registered_meta():
    for meta in catalog.all_meta({"ADMIN_TASKS_SELFTEST": "1"}):
        fields = taskform.fields_for(meta)
        assert fields and all(f.supported for f in fields), meta.name
        assert taskform.can_submit(fields)
    kinds = {f.name: f.kind for f in taskform.fields_for(responses_backfill.META)}
    assert kinds == {"stores": "enum", "batch_size": "int", "workspace_id": "text", "form_ids": "lines"}
    assert {f.name: f.kind for f in taskform.fields_for(selftest_slow.META)}["decline"] == "bool"


def test_unsupported_shapes_render_nothing_and_block_a_required_one():
    from typing import Union

    from backend.admin.tasks.spec import Params, TaskMeta
    import enum

    class P(Params):
        odd: Union[int, str] = 1
        needed: dict = {}

    class Q(Params):
        odd: Union[int, str]

    class E(str, enum.Enum):
        x = "x"

    class R(selftest.SelfTestResult.__base__):
        pass

    for params, submit in ((P, True), (Q, False)):
        meta = TaskMeta("t", 1, params, selftest.SelfTestResult, E, False)
        fields = taskform.fields_for(meta)
        assert not any(f.supported for f in fields if f.name in ("odd", "needed"))
        assert taskform.can_submit(fields) is submit


def test_form_parsing_and_validation_never_echo_values():
    meta = responses_backfill.META
    fields = taskform.fields_for(meta)
    hostile = "<script>alert('x')</script>"
    form = {"p_stores": "auto", "p_batch_size": "500", "p_workspace_id": hostile, "p_form_ids": "a1\n\n b2 \n"}
    parsed = taskform.parse(meta, fields, form)
    assert parsed.params is None and parsed.bad == {"workspace_id"}
    ok = taskform.parse(meta, fields, {**form, "p_workspace_id": "", "p_stores": "mongo", "p_batch_size": ""})
    assert ok.params == {"stores": "mongo", "batch_size": 500, "workspace_id": None, "form_ids": ["a1", "b2"]}
    for bad in ({"p_batch_size": "50"}, {"p_batch_size": "5x"}, {"p_stores": "all"}, {"p_form_ids": "\n".join("a" * 1 for _ in range(101))}):
        assert taskform.parse(meta, fields, {**form, "p_workspace_id": "", **bad}).params is None


async def test_validation_errors_do_not_echo_values_and_keep_the_good_fields(ctx):
    hostile = '"><img src=x onerror=alert(1)>'
    response = await ctx.post(
        "/tasks/responses.backfill_workspaces/dry-run",
        {"p_stores": "mongo", "p_batch_size": "999", "p_workspace_id": hostile, "p_form_ids": "ok1\nok2"},
    )
    assert response.status_code == 400
    html = response.text
    assert hostile not in html and "onerror" not in html and "&lt;img" not in html
    assert "were not accepted" in html and 'aria-invalid="true"' in html
    assert re.search(r'<option value="mongo" selected', html) and 'value="999"' in html
    assert "ok1\nok2" in html
    response = await ctx.post("/tasks/responses.backfill_workspaces/dry-run", {"p_batch_size": "99999999999999999"})
    assert response.status_code == 400 and "99999999999999999" not in response.text
    assert await ctx.runs() == []


async def test_hostile_free_text_is_escaped_where_it_is_shown(ctx):
    """Parameters and requester names are rendered escaped on every page."""
    run_id = await ctx.dry_run("selftest", {"rounds": "1"})
    async with ctx.portal.engine.begin() as conn:
        request = signing.RunRequest.create(
            task="selftest", version=1, params={"rounds": 1, "decline": False}, dry_run=True,
            requested_by='<b onmouseover="x">evil@example.org', requested_at=ctx.clock.now(),
        )
        await ctx.portal.tasks._insert(conn, request)
    for path in ("/tasks/runs", f"/tasks/runs/{request.id}", f"/tasks/runs/{run_id}"):
        html = (await ctx.b.get(path)).text
        assert '<b onmouseover' not in html, path
    assert "&lt;b onmouseover" in (await ctx.b.get(f"/tasks/runs/{request.id}")).text


# -- dry run -----------------------------------------------------------------------------------
async def test_dry_run_inserts_a_signed_queued_row_and_audits(ctx):
    run_id = await ctx.dry_run(SLOW, {"items": "10", "batch_size": "5"})
    (row,) = await ctx.runs(SLOW)
    assert str(row["id"]) == run_id and row["state"] == "queued" and row["dry_run"] is True
    assert row["requested_by"] == ADMIN and row["resumes_run_id"] is None
    assert row["params"] == {"items": 10, "batch_size": 5, "emit_events": 0, "fail_at": -1, "decline": False, "write_probe": False}
    assert signing.verify_request(dict(row))
    (entry,) = await ctx.audit_rows("task.run.requested")
    assert entry["actor_kind"] == "admin" and entry["actor_email"] == ADMIN and entry["target_id"] == run_id
    assert entry["detail"]["dry_run"] is True and entry["detail"]["requested_by"] == ADMIN
    assert entry["after"]["params"]["items"] == 10 and "params_hash" not in json.dumps(entry["detail"])
    assert entry["detail"]["params_digest"] == row["params_hash"][:16]
    async with ctx.owner.connect() as conn:
        assert (await audit.verify_chain(conn, None, None)).ok


async def test_dry_run_is_rate_limited_per_admin(ctx):
    for _ in range(10):
        assert (await ctx.post("/tasks/selftest/dry-run", {"p_rounds": "1"})).status_code == 303
    limited = await ctx.post("/tasks/selftest/dry-run", {"p_rounds": "1"})
    assert limited.status_code == 429 and "Too many dry runs" in limited.text
    assert len(await ctx.runs("selftest")) == 10
    ctx.clock.advance(301)
    assert (await ctx.post("/tasks/selftest/dry-run", {"p_rounds": "1"})).status_code == 303


async def test_oversized_params_are_refused(ctx):
    ids = "\n".join(f"a{i:062d}" for i in range(100))
    response = await ctx.post("/tasks/responses.backfill_workspaces/dry-run", {"p_form_ids": ids})
    assert response.status_code == 303  # 100 * 66 bytes fits
    from backend.admin.services.task_pages import MAX_PARAMS_BYTES, Refusal

    assert len(signing.canonical_params({"x": "y" * 9000})) > MAX_PARAMS_BYTES
    started = await ctx.portal.tasks.request_run(
        ctx.session, selftest.META, {"x": "y" * 9000}, True, IP, UA, None
    )
    assert started.refusal is Refusal.params_too_large


# -- apply: prepare, confirm, prior dry run ------------------------------------------------------
async def test_apply_without_a_prior_dry_run_is_refused_before_a_code_is_spent(ctx):
    before = len(ctx.codes)
    response = await ctx.prepare("apply", {"task": GUARDED, "p_items": "10"})
    assert response.status_code == 409 and "needs a successful dry run" in response.text
    assert TOKEN_FIELD.search(response.text) is None
    assert await ctx.runs() == []
    assert len(ctx.codes) == before - 1  # the code was posted, but nothing was verified or burnt server-side
    assert (await ctx.audit_rows("task.run.requested")) == []


async def test_apply_after_a_matching_dry_run_and_the_real_runner_accepts_it(ctx):
    params = {"items": "10", "batch_size": "5"}
    dry_id = await ctx.dry_run(GUARDED, params)
    assert await ctx.drain() == 1
    dry = (await ctx.runs(GUARDED))[0]
    assert dry["state"] == "succeeded"
    # before the dry run finished, an apply would have been refused; now time moves on
    ctx.clock.advance(10)
    page = (await ctx.b.get(f"/tasks/{GUARDED}")).text
    assert "Last dry run" in page and f"/tasks/runs/{dry_id}" in page

    # different params: refused
    mismatch, _ = await ctx.apply(GUARDED, {"items": "11", "batch_size": "5"}, expect=409)
    assert "dry run" in mismatch.text and TOKEN_FIELD.search(mismatch.text) is None

    prepared, final = await ctx.apply(GUARDED, params)
    assert "Confirm: apply" in prepared.text and "works once" in prepared.text
    assert final.status_code == 303 and final.headers["location"].endswith("?notice=started")
    rows = await ctx.runs(GUARDED)
    real = [r for r in rows if not r["dry_run"]][0]
    assert real["state"] == "queued" and signing.verify_request(dict(real))
    assert real["params_hash"] == dry["params_hash"]

    # the runner's claim path verifies the signature, the prior dry run and the params
    assert await ctx.drain() == 1
    done = (await ctx.sql("SELECT * FROM tasks.runs WHERE id = :i", i=real["id"]))[0]
    assert done["state"] == "succeeded" and done["refusal_code"] is None
    assert done["result"] == {"changed": 10, "unchanged": 0, "batches": 2}

    page = (await ctx.b.get(f"/tasks/runs/{real['id']}")).text
    assert "succeeded" in page and "changed" in page and "<code>batches</code>" in page
    api = (await ctx.b.get(f"/api/tasks/runs/{real['id']}?after=0")).json()
    assert api["state"] == "succeeded" and api["terminal"] is True and api["done"] == 10 and api["percent"] == 100
    assert [e["code"] for e in api["events"]] == ["batch_done", "batch_done"]
    after = (await ctx.b.get(f"/api/tasks/runs/{real['id']}?after={api['events'][0]['seq']}")).json()
    assert len(after["events"]) == 1

    requested = await ctx.audit_rows("task.run.requested")
    assert [r["detail"]["dry_run"] for r in requested] == [True, False]
    assert requested[1]["actor_kind"] == "admin"
    async with ctx.owner.connect() as conn:
        assert (await audit.verify_chain(conn, None, None)).ok


async def test_a_dry_run_that_finished_after_the_request_or_over_a_day_ago_does_not_count(ctx):
    params = {"items": "10", "batch_size": "5"}
    await ctx.dry_run(GUARDED, params)
    await ctx.drain()
    meta = selftest_slow.GUARDED_META
    canonical = meta.params.model_validate({"items": 10, "batch_size": 5}).model_dump(mode="json")
    # the runner's clock stamped finished_at == now: not yet "before now"
    assert not await ctx.portal.tasks.prior_dry_run_exists(meta, canonical)
    ctx.clock.advance(5)
    assert await ctx.portal.tasks.prior_dry_run_exists(meta, canonical)
    ctx.clock.advance(24 * 3600)
    assert not await ctx.portal.tasks.prior_dry_run_exists(meta, canonical)


async def test_a_failed_code_issues_no_token_and_a_good_one_is_bound_to_the_page_params(ctx):
    wrong = await ctx.post("/tasks/prepare", {"action": "apply", "task": SLOW, "code": "000000", "p_items": "10"})
    assert wrong.status_code == 200 and "did not work" in wrong.text and TOKEN_FIELD.search(wrong.text) is None
    blank = await ctx.post("/tasks/prepare", {"action": "apply", "task": SLOW, "p_items": "10"})
    assert blank.status_code == 200 and TOKEN_FIELD.search(blank.text) is None and "did not work" not in blank.text
    assert await ctx.runs() == []


async def test_the_apply_confirmation_round_trips_lists_and_hidden_fields(ctx):
    # selftest_slow has no list parameter; the backfill task needs the runner's store, so only
    # the confirmation page and the queued row are checked (the runner is not run here)
    params = {"stores": "mongo", "batch_size": "200", "workspace_id": "ws-1", "form_ids": "f1\nf2\nf3"}
    await ctx.dry_run("responses.backfill_workspaces", params)
    (row,) = await ctx.runs("responses.backfill_workspaces")
    owner_conn = ctx.owner
    async with owner_conn.begin() as conn:
        await conn.execute(
            text("UPDATE tasks.runs SET state='running', started_at=:n, runner_id='r', heartbeat_at=:n WHERE id=:i"),
            {"n": ctx.clock.now(), "i": row["id"]},
        )
        await conn.execute(
            text("UPDATE tasks.runs SET state='succeeded', finished_at=:n WHERE id=:i"),
            {"n": ctx.clock.now() - timedelta(seconds=30), "i": row["id"]},
        )
    prepared, final = await ctx.apply("responses.backfill_workspaces", params)
    assert "f1, f2, f3" in prepared.text and "ws-1" in prepared.text
    assert final.status_code == 303
    real = [r for r in await ctx.runs("responses.backfill_workspaces") if not r["dry_run"]][0]
    assert real["params"] == {"stores": "mongo", "batch_size": 200, "workspace_id": "ws-1", "form_ids": ["f1", "f2", "f3"]}
    assert real["params_hash"] == row["params_hash"]


# -- cancel ----------------------------------------------------------------------------------
async def test_cancel_semantics(ctx):
    run_id = await ctx.dry_run(SLOW, {"items": "10"})
    assert "Cancel the run..." in (await ctx.b.get(f"/tasks/runs/{run_id}")).text
    wrong = await ctx.post("/tasks/prepare", {"action": "cancel", "run_id": run_id, "code": "000000"})
    assert TOKEN_FIELD.search(wrong.text) is None
    prepared = await ctx.prepare("cancel", {"run_id": run_id})
    token = TOKEN_FIELD.search(prepared.text).group(1)
    response = await ctx.post(f"/tasks/runs/{run_id}/cancel", {"stepup_token": token})
    assert response.status_code == 303 and response.headers["location"].endswith("notice=cancel_requested")
    (row,) = await ctx.runs(SLOW)
    assert row["cancel_requested_at"] is not None and row["state"] == "queued"
    assert len(await ctx.audit_rows("task.run.cancel_requested")) == 1
    # idempotent: the page says it was already requested; a direct replay changes nothing
    again_page = await ctx.prepare("cancel", {"run_id": run_id})
    assert again_page.status_code == 200 and "already requested" in again_page.text
    token = ctx.portal.stepup.issue(ctx.session, action_hash("tasks.cancel", run_id))
    again = await ctx.post(f"/tasks/runs/{run_id}/cancel", {"stepup_token": token})
    assert again.status_code == 303 and "cancel_again" in again.headers["location"]
    assert len(await ctx.audit_rows("task.run.cancel_requested")) == 1
    # the runner honours it before starting
    await ctx.drain()
    assert (await ctx.runs(SLOW))[0]["state"] == "cancelled"
    # a finished run cannot be cancelled
    refused = await ctx.prepare("cancel", {"run_id": run_id})
    assert refused.status_code == 409 and "cannot be cancelled" in refused.text
    token = ctx.portal.stepup.issue(ctx.session, action_hash("tasks.cancel", run_id))
    direct = await ctx.post(f"/tasks/runs/{run_id}/cancel", {"stepup_token": token})
    assert direct.status_code == 409 and len(await ctx.audit_rows("task.run.cancel_requested")) == 1


async def test_admin_role_cannot_update_anything_but_the_cancel_column(ctx):
    run_id = await ctx.dry_run(SLOW, {"items": "10"})
    for column, value in (("state", "'succeeded'"), ("result", "'{}'::jsonb"), ("params_hash", "repeat('0', 64)")):
        with pytest.raises(Exception):
            async with ctx.portal.engine.begin() as conn:
                await conn.execute(text(f"UPDATE tasks.runs SET {column} = {value} WHERE id = :i"), {"i": run_id})


# -- resume ------------------------------------------------------------------------------------
async def _finish(ctx, run_id, state, code=None):
    async with ctx.owner.begin() as conn:
        await conn.execute(
            text("UPDATE tasks.runs SET state='running', started_at=:n, runner_id='r', heartbeat_at=:n WHERE id=:i AND state='queued'"),
            {"n": ctx.clock.now(), "i": run_id},
        )
        await conn.execute(
            text("UPDATE tasks.runs SET state=:s, finished_at=:n, refusal_code=:c WHERE id=:i"),
            {"s": state, "n": ctx.clock.now(), "c": code, "i": run_id},
        )


async def test_resume_creates_a_signed_request_with_resumes_run_id_and_the_runner_runs_it(ctx):
    run_id = await ctx.dry_run(SLOW, {"items": "20", "batch_size": "5", "fail_at": "7"})
    assert await ctx.drain() == 1
    failed = (await ctx.runs(SLOW))[0]
    assert failed["state"] == "failed"
    page = (await ctx.b.get(f"/tasks/runs/{run_id}")).text
    assert "Resume..." in page and "failed" in page
    ctx.clock.advance(5)
    prepared = await ctx.prepare("resume", {"run_id": run_id})
    assert "Confirm: resume run" in prepared.text
    resumed = await ctx.post(f"/tasks/runs/{run_id}/resume", {"stepup_token": TOKEN_FIELD.search(prepared.text).group(1)})
    assert resumed.status_code == 303 and "resume_started" in resumed.headers["location"]
    new = [r for r in await ctx.runs(SLOW) if r["resumes_run_id"]][0]
    assert str(new["resumes_run_id"]) == run_id and new["params_hash"] == failed["params_hash"]
    assert new["dry_run"] is True and signing.verify_request(dict(new))
    (entry,) = [e for e in await ctx.audit_rows("task.run.requested") if e["detail"].get("resumes_run_id")]
    assert entry["detail"]["resumes_run_id"] == run_id
    # while the resume is queued, a second one is refused
    again = await ctx.prepare("resume", {"run_id": run_id})
    assert again.status_code == 409 and "already queued or running" in again.text
    # a token for another run id does not work
    tok = ctx.portal.stepup.issue(ctx.session, action_hash("tasks.resume", uuid.uuid4(), failed["params_hash"]))
    assert (await ctx.post(f"/tasks/runs/{run_id}/resume", {"stepup_token": tok})).status_code == 403


async def test_resume_refusals_from_the_portal_and_the_runners_codes_are_shown(ctx):
    # not resumable task, and a run that is not in an end state
    ro = await ctx.dry_run(GUARDED, {"items": "10"})
    await _finish(ctx, ro, "failed")
    page = (await ctx.b.get(f"/tasks/runs/{ro}")).text
    assert "Resume..." not in page and "cannot be resumed" in page
    refused = await ctx.prepare("resume", {"run_id": ro})
    assert refused.status_code == 409 and "cannot be resumed" in refused.text
    queued = await ctx.dry_run(SLOW, {"items": "10"})
    queued_refused = await ctx.prepare("resume", {"run_id": queued})
    assert queued_refused.status_code == 409 and "Only a failed, interrupted or cancelled run" in queued_refused.text

    # codes the runner records after the fact are explained on the run page
    for code, words in (
        ("not_resumable", "cannot be resumed"),
        ("resume_mismatch", "does not match this request"),
        ("already_resumed", "already resumed to completion"),
        ("dry_run_required", "no successful dry run"),
        ("declined", "declined to run"),
    ):
        run = await ctx.dry_run("selftest", {"rounds": "1"})
        await _finish(ctx, run, "refused", code)
        html = (await ctx.b.get(f"/tasks/runs/{run}")).text
        assert f"<code>{code}</code>" in html and words in html, code


async def test_runner_refusal_for_a_resume_is_visible(ctx):
    first = await ctx.dry_run(SLOW, {"items": "10"})
    await _finish(ctx, first, "failed")
    async with ctx.portal.engine.begin() as conn:
        row = (await ctx.sql("SELECT * FROM tasks.runs WHERE id = :i", i=first))[0]
        # a signed resume against a *different* params hash cannot come from the portal;
        # forge one with the signing helper to see the runner's code on the page
        request = signing.RunRequest.create(
            task=SLOW, version=1, params={"items": 11, "batch_size": 5, "emit_events": 0, "fail_at": -1, "decline": False, "write_probe": False},
            dry_run=True, requested_by=ADMIN, requested_at=ctx.clock.now(), resumes_run_id=row["id"],
        )
        await ctx.portal.tasks._insert(conn, request)
    assert await ctx.drain() == 1
    html = (await ctx.b.get(f"/tasks/runs/{request.id}")).text
    assert "<code>resume_mismatch</code>" in html


# -- history, progress, pages ------------------------------------------------------------------
async def test_history_filters_paging_and_validation(ctx):
    for _ in range(3):
        await ctx.dry_run("selftest", {"rounds": "1"})
    assert await ctx.drain() == 3
    await ctx.dry_run(SLOW, {"items": "10"})
    html = (await ctx.b.get("/tasks/runs")).text
    assert html.count("/tasks/runs/") >= 4 and "succeeded" in html and "queued" in html
    only = (await ctx.b.get("/tasks/runs?task=selftest&state=succeeded")).text
    assert "selftest_slow" not in only.split("<tbody>")[1]
    for bad in ("?task=nope", "?state=weird", "?task=%3Cscript%3E"):
        response = await ctx.b.get("/tasks/runs" + bad)
        assert response.status_code == 400 and "<script>" not in response.text
    assert (await ctx.b.get("/tasks/runs?page=abc")).status_code == 200
    assert (await ctx.b.get("/tasks/runs?page=99")).status_code == 200


async def test_run_page_and_api_for_missing_or_malformed_ids(ctx):
    assert (await ctx.b.get("/tasks/runs/not-a-uuid")).status_code == 404
    assert (await ctx.b.get(f"/tasks/runs/{uuid.uuid4()}")).status_code == 404
    api = await ctx.b.get(f"/api/tasks/runs/{uuid.uuid4()}")
    assert api.status_code == 404 and api.json() == {"error": "not_found"}
    assert (await ctx.b.get("/api/tasks/runs/xyz")).status_code == 404


async def test_event_paging_and_sanitised_events(ctx):
    run_id = await ctx.dry_run(SLOW, {"items": "20", "batch_size": "1", "emit_events": "1"})
    await ctx.drain()
    rid = uuid.UUID(run_id)
    async with ctx.owner.begin() as conn:
        base = (await conn.execute(text("SELECT coalesce(max(seq), 0) FROM tasks.run_events WHERE run_id=:i"), {"i": rid})).scalar()
        await conn.execute(
            text("INSERT INTO tasks.run_events (run_id, seq, code, counts, ids, error_class) "
                 "VALUES (:i, :s, 'note', CAST(:c AS jsonb), CAST(:d AS jsonb), 'ValueError')"),
            {"i": rid, "s": base + 1, "c": json.dumps({"seen": 3, "bad key": 4, "txt": "x"}), "d": json.dumps(["ok-1", "<b>no</b>", "has space"])},
        )
    html = (await ctx.b.get(f"/tasks/runs/{run_id}")).text
    assert "seen=3" in html and "bad key" not in html and "txt=" not in html
    assert "<code>ok-1</code>" in html and "&lt;b&gt;" not in html and "has space" not in html
    assert "ValueError" in html
    api = (await ctx.b.get(f"/api/tasks/runs/{run_id}?after={base}")).json()
    assert [e["counts"] for e in api["events"]] == [{"seen": 3}] and api["events"][0]["ids"] == ["ok-1"]
    # paging: 50 per page, a link to the next
    async with ctx.owner.begin() as conn:
        for i in range(60):
            await conn.execute(
                text("INSERT INTO tasks.run_events (run_id, seq, code) VALUES (:i, :s, 'note')"),
                {"i": rid, "s": base + 10 + i},
            )
    page = (await ctx.b.get(f"/tasks/runs/{run_id}")).text
    assert "Later events" in page
    nxt = re.search(r'href="(/tasks/runs/[0-9a-f-]+\?after=\d+)"', page).group(1)
    assert (await ctx.b.get(nxt)).status_code == 200


async def test_progress_and_live_markup(ctx):
    run_id = await ctx.dry_run(SLOW, {"items": "20", "batch_size": "5"})
    async with ctx.owner.begin() as conn:
        await conn.execute(
            text("UPDATE tasks.runs SET state='running', started_at=:n, runner_id='r', heartbeat_at=:n, progress='{\"done\": 5, \"total\": 20}' WHERE id=:i"),
            {"n": ctx.clock.now(), "i": uuid.UUID(run_id)},
        )
    html = (await ctx.b.get(f"/tasks/runs/{run_id}")).text
    assert '<progress id="progress" max="100" value="25"' in html and "5 / 20" in html
    assert 'id="live-indicator"' in html and "hidden" in html and ">Refresh</a>" in html
    assert '<script src="/static/tasks.js" defer></script>' in html and html.count("<script") == 1
    api = (await ctx.b.get(f"/api/tasks/runs/{run_id}")).json()
    assert api["state"] == "running" and api["percent"] == 25 and api["terminal"] is False
    js = await ctx.b.get("/static/tasks.js")
    assert js.status_code == 200 and js.headers["content-type"].startswith("text/javascript")
    assert "innerHTML" not in js.text and "eval(" not in js.text
    # a finished run does not load the poller's work (the page still carries the file)
    await _finish(ctx, run_id, "succeeded")
    assert 'data-terminal="yes"' in (await ctx.b.get(f"/tasks/runs/{run_id}")).text


async def test_run_result_renders_only_through_the_result_schema(ctx):
    run_id = await ctx.dry_run("selftest", {"rounds": "2"})
    await ctx.drain()
    html = (await ctx.b.get(f"/tasks/runs/{run_id}")).text
    assert "<code>ok</code>" in html and "<code>checked</code>" in html
    async with ctx.owner.begin() as conn:
        await conn.execute(
            text("UPDATE tasks.runs SET result = CAST(:r AS jsonb) WHERE id = :i"),
            {"r": json.dumps({"ok": True, "checked": 2, "leak": "sk_live_planted"}), "i": uuid.UUID(run_id)},
        )
    html = (await ctx.b.get(f"/tasks/runs/{run_id}")).text
    assert "sk_live_planted" not in html and "does not match" in html


async def test_secrets_never_appear_in_any_task_response(ctx):
    planted = "ghp_PlantedSecretValue0123456789abcdef"
    run_id = await ctx.dry_run("selftest", {"rounds": "1"})
    await ctx.drain()
    await ctx.post("/tasks/responses.backfill_workspaces/dry-run", {"p_workspace_id": planted + "!"})
    pages = ["/tasks", "/tasks/selftest", "/tasks/runs", f"/tasks/runs/{run_id}", f"/api/tasks/runs/{run_id}",
             "/tasks/responses.backfill_workspaces"]
    for path in pages:
        body = (await ctx.b.get(path)).text
        assert planted not in body, path
        for needle in ("SETTINGS_MASTER_KEY=", "request_sig", "nonce"):
            assert needle not in body, (path, needle)
    prepared = await ctx.prepare("apply", {"task": SLOW, "p_items": "10"})
    assert "request_sig" not in prepared.text


# -- structure and audit -----------------------------------------------------------------------
class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.h1 = 0
        self.ids, self.label_for, self.fields, self.tables = set(), set(), [], []
        self.landmarks, self.skip, self._table = set(), False, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.h1 += tag == "h1"
        if tag in ("nav", "main", "header"):
            self.landmarks.add(tag)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "label" and a.get("for"):
            self.label_for.add(a["for"])
        if tag in ("input", "select", "textarea") and a.get("type") != "hidden":
            self.fields.append((a.get("id"), a.get("aria-label")))
        if tag == "progress":
            self.fields.append((None, a.get("aria-label")))
        if tag == "a" and a.get("href") == "#main":
            self.skip = True
        if tag == "table":
            self._table = [False, False, False]
            self.tables.append(self._table)
        if tag == "caption" and self._table:
            self._table[0] = True
        if tag == "th" and a.get("scope") == "col" and self._table:
            self._table[1] = True
        if tag == "th" and a.get("scope") == "row" and self._table:
            self._table[2] = True


async def test_pages_are_structurally_accessible_and_csp_clean(ctx):
    run_id = await ctx.dry_run(SLOW, {"items": "10"})
    await ctx.drain()
    prepared = await ctx.prepare("apply", {"task": SLOW, "p_items": "10"})
    pages = {
        "/tasks": None, "/tasks/runs": None, f"/tasks/runs/{run_id}": None,
        f"/tasks/{SLOW}": None, "/tasks/responses.backfill_workspaces": None,
    }
    htmls = {path: await ctx.b.get(path) for path in pages}
    htmls["confirm"] = prepared
    for path, response in htmls.items():
        assert response.status_code == 200, path
        html = response.text
        assert "script-src 'self'" in response.headers["content-security-policy"]
        stripped = re.sub(r'<script src="/static/tasks\.js" defer></script>', "", html)
        assert not re.search(r"<script|<style|\sstyle=|\son\w+\s*=|(src|href|action)=[\"']?(https?:)?//", stripped, re.I), path
        s = Structure()
        s.feed(html)
        assert s.h1 == 1 and {"nav", "main", "header"} <= s.landmarks and s.skip and "main" in s.ids, path
        for field_id, aria in s.fields:
            assert aria or (field_id and field_id in s.label_for), (path, field_id)
        for caption, header, row in s.tables:
            assert caption or header or row, path
        assert 'aria-current="page">Tasks' in html


async def test_every_changing_action_is_audited_with_the_admin_and_masked_params(ctx):
    await ctx.dry_run("responses.backfill_workspaces", {"workspace_id": "ws-9"})
    (entry,) = await ctx.audit_rows("task.run.requested")
    assert entry["after"]["params"]["workspace_id"] == "ws-9"
    assert entry["actor_email"] == ADMIN and entry["ip"] and entry["session_id"]
    assert entry["request_id"] is None or isinstance(entry["request_id"], str)


def test_catalog_names_do_not_collide_with_literal_routes():
    for meta in catalog.all_meta({"ADMIN_TASKS_SELFTEST": "1"}):
        assert meta.name not in ("runs", "prepare")


async def test_real_runs_and_their_cancel_enqueue_the_admin_notice_in_the_same_transaction(ctx):
    await ctx.dry_run(SLOW, {"items": "10"})
    assert await ctx.sql("SELECT 1 FROM admin.notifications") == []  # a dry run is not mailed
    _, final = await ctx.apply(SLOW, {"items": "10", "batch_size": "5"})
    assert final.status_code == 303
    run_id = final.headers["location"].split("?")[0].rsplit("/", 1)[1]
    prepared = await ctx.prepare("cancel", {"run_id": run_id})
    await ctx.post(f"/tasks/runs/{run_id}/cancel", {"stepup_token": TOKEN_FIELD.search(prepared.text).group(1)})
    rows = await ctx.sql("SELECT kind, payload, audit_seq, dedupe_key FROM admin.notifications ORDER BY id")
    assert [r["kind"] for r in rows] == ["tasks.run", "tasks.run"]
    assert rows[0]["payload"] == {"task": SLOW, "run_id": run_id, "state": "queued", "actor": ADMIN}
    assert rows[1]["payload"]["state"] == "cancel_requested"
    assert all("params" not in json.dumps(r["payload"]) for r in rows)
    audited = {r["seq"] for r in await ctx.sql("SELECT seq FROM admin.audit_log")}
    assert {r["audit_seq"] for r in rows} <= audited
    assert len({r["dedupe_key"] for r in rows}) == 2
