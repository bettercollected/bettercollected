"""Saved views of a form's report: a name, a scope (``private`` or ``form``) and a
validated definition. Who sees, makes, changes and deletes which, the checks
that keep an answer out of a stored view, the limits, the audit entries of what
the whole form shares, the clean-up with a form or a member, and the permissions
of the routes themselves. Everything here is synthetic."""

import json

import pytest
from sqlalchemy import text

from backend.app.container import container
from backend.app.schemas.form_access_grant import ROLE_VIEWER
from backend.app.schemas.workspace_audit_event import (
    REPORT_EVENTS,
    REPORT_VIEW_CREATED,
    REPORT_VIEW_DELETED,
    REPORT_VIEW_SHARED,
    REPORT_VIEW_UNSHARED,
    REPORT_VIEW_UPDATED,
)
from backend.app.services.reporting import limits
from tests.app.controllers.data import testUser
from tests.app.form_access.helpers import add_member, audit_events, cookies, fail_audit, grant, restrict
from tests.app.reporting.helpers import (
    add_response,
    answer_choice,
    card,
    definition,
    make_form,
    query,
    report_url,
    survey_fields,
)

pytestmark = pytest.mark.asyncio

DEFINITION = definition(card("dept", "bar", dimension="q:dept"), card("n", "tile"))


def views(workspace, form, tail=""):
    return report_url(workspace, form, "views" + tail)


async def call(client, method, workspace, form, tail="", user=testUser, **kwargs):
    return await getattr(client, method)(views(workspace, form, tail), cookies=cookies(user), **kwargs)


async def save(client, workspace, form, name="Overview", scope="private", user=testUser, body=None):
    payload = body or {"name": name, "scope": scope, "definition": DEFINITION}
    return await call(client, "post", workspace, form, user=user, json=payload)


async def listed(client, workspace, form, user=testUser):
    response = await call(client, "get", workspace, form, user=user)
    assert response.status_code == 200, response.text
    return response.json()["views"]


@pytest.fixture()
async def world(workspace, reporting_on):
    form = await make_form(workspace, survey_fields())
    await add_response(workspace, form, {"dept": answer_choice("care")})
    people = {
        "viewer": await add_member(workspace, "VIEWER"),
        "viewer2": await add_member(workspace, "VIEWER"),
        "editor": await add_member(workspace, "EDITOR"),
        "editor2": await add_member(workspace, "EDITOR"),
        "admin": await add_member(workspace, "ADMIN"),
        "officer": await add_member(workspace, "PRIVACY_OFFICER"),
    }
    return workspace, form, people


# ------------------------------------------------------------------ private views


async def test_a_private_view_is_its_makers_alone_whoever_else_asks(client, world):
    workspace, form, people = world
    made = await save(client, workspace, form, "My notes", user=people["viewer"])
    assert made.status_code == 201, made.text
    view = made.json()
    assert view["scope"] == "private" and view["mine"] is True and view["revision"] == 1
    assert view["canEdit"] is True and view["canDelete"] is True
    assert [v["id"] for v in await listed(client, workspace, form, people["viewer"])] == [view["id"]]
    # not another member, not an admin, not the owner of the workspace
    for who in ("viewer2", "editor", "admin"):
        assert await listed(client, workspace, form, people[who]) == []
        for method, extra in (("get", {}), ("patch", {"json": {"revision": 1, "name": "x"}}), ("delete", {})):
            gone = await call(client, method, workspace, form, "/" + view["id"], user=people[who], **extra)
            assert gone.status_code == 404 and gone.json()["code"] == "view_not_found", (who, method)
    assert await listed(client, workspace, form) == []
    unknown = await call(client, "get", workspace, form, "/" + "a" * 24, user=people["viewer"])
    assert unknown.status_code == 404 and unknown.json()["code"] == "view_not_found"
    assert (await call(client, "get", workspace, form, "/not-an-id", user=people["viewer"])).status_code == 404


async def test_a_private_view_is_the_default_and_needs_no_form_edit(client, world):
    workspace, form, people = world
    made = await save(client, workspace, form, body={"name": "Mine", "definition": DEFINITION}, user=people["viewer"])
    assert made.status_code == 201 and made.json()["scope"] == "private"


async def test_the_owner_edits_and_deletes_their_own_private_view(client, world):
    workspace, form, people = world
    view = (await save(client, workspace, form, "One", user=people["viewer"])).json()
    renamed = await call(client, "patch", workspace, form, "/" + view["id"], user=people["viewer"], json={"revision": 1, "name": "  Two  "})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Two" and renamed.json()["revision"] == 2
    again = await call(client, "get", workspace, form, "/" + view["id"], user=people["viewer"])
    assert again.json()["name"] == "Two"
    assert (await call(client, "delete", workspace, form, "/" + view["id"], user=people["viewer"])).status_code == 204
    assert await listed(client, workspace, form, people["viewer"]) == []
    assert (await call(client, "delete", workspace, form, "/" + view["id"], user=people["viewer"])).status_code == 404


# ------------------------------------------------------------------- form views


async def test_a_view_for_the_form_needs_form_edit_to_make(client, world):
    workspace, form, people = world
    for who in ("viewer", "officer"):
        refused = await save(client, workspace, form, "Shared", scope="form", user=people[who])
        assert refused.status_code == 403, (who, refused.text)
    made = await save(client, workspace, form, "Shared", scope="form", user=people["editor"])
    assert made.status_code == 201 and made.json()["scope"] == "form"
    seen = (await listed(client, workspace, form, people["viewer"]))[0]
    assert seen["id"] == made.json()["id"] and seen["mine"] is False
    assert seen["canEdit"] is False and seen["canDelete"] is False
    editor_two = (await listed(client, workspace, form, people["editor2"]))[0]
    assert editor_two["canEdit"] is True and editor_two["canDelete"] is False
    admin = (await listed(client, workspace, form, people["admin"]))[0]
    assert admin["canEdit"] is True and admin["canDelete"] is True


async def test_the_form_views_are_seen_by_everyone_who_may_open_the_report_and_run(client, world):
    workspace, form, people = world
    made = (await save(client, workspace, form, "Shared", scope="form", user=people["editor"])).json()
    for who in ("viewer", "viewer2", "admin"):
        got = await call(client, "get", workspace, form, "/" + made["id"], user=people[who])
        assert got.status_code == 200 and got.json()["definition"]["cards"][0]["id"] == "dept"
        # the stored definition runs as a query does
        ran = await query(client, workspace, form, got.json()["definition"], user=people[who])
        assert ran.status_code == 200, ran.text
    # a Privacy officer reads nothing derived from answers, views included
    assert (await call(client, "get", workspace, form, user=people["officer"])).status_code == 403


async def test_who_changes_and_deletes_a_form_view(client, world):
    workspace, form, people = world
    by_editor = (await save(client, workspace, form, "By editor", scope="form", user=people["editor"])).json()
    url = "/" + by_editor["id"]
    # a reader cannot change or delete it
    assert (await call(client, "patch", workspace, form, url, user=people["viewer"], json={"revision": 1, "name": "x"})).status_code == 403
    assert (await call(client, "delete", workspace, form, url, user=people["viewer"])).status_code == 403
    # another editor changes it (it is the form's) but cannot delete someone else's
    assert (await call(client, "patch", workspace, form, url, user=people["editor2"], json={"revision": 1, "name": "Renamed"})).status_code == 200
    assert (await call(client, "delete", workspace, form, url, user=people["editor2"])).status_code == 403
    # nobody but its maker takes it back to private
    taken = await call(client, "patch", workspace, form, url, user=people["editor2"], json={"revision": 2, "scope": "private"})
    assert taken.status_code == 403
    # an admin moderates: deletes it
    assert (await call(client, "delete", workspace, form, url, user=people["admin"])).status_code == 204
    # its maker deletes their own
    own = (await save(client, workspace, form, "Own", scope="form", user=people["editor"])).json()
    assert (await call(client, "delete", workspace, form, "/" + own["id"], user=people["editor"])).status_code == 204


async def test_sharing_and_taking_back_a_view(client, world):
    workspace, form, people = world
    view = (await save(client, workspace, form, "Mine", user=people["editor"])).json()
    url = "/" + view["id"]
    # a reader cannot share even their own
    mine = (await save(client, workspace, form, "Reader's", user=people["viewer"])).json()
    refused = await call(client, "patch", workspace, form, "/" + mine["id"], user=people["viewer"], json={"revision": 1, "scope": "form"})
    assert refused.status_code == 403
    shared = await call(client, "patch", workspace, form, url, user=people["editor"], json={"revision": 1, "scope": "form"})
    assert shared.status_code == 200 and shared.json()["scope"] == "form"
    assert [v["name"] for v in await listed(client, workspace, form, people["viewer2"])] == ["Mine"]
    private = await call(client, "patch", workspace, form, url, user=people["editor"], json={"revision": 2, "scope": "private"})
    assert private.status_code == 200 and private.json()["scope"] == "private" and private.json()["revision"] == 3
    assert await listed(client, workspace, form, people["viewer2"]) == []


# ------------------------------------------------------------ what is stored


async def test_the_stored_definition_is_what_a_query_accepts_and_holds_no_answer(client, world):
    workspace, form, people = world
    made = (await save(client, workspace, form, "Checked", user=people["viewer"])).json()
    stored = made["definition"]
    assert stored["v"] == 1 and [c["id"] for c in stored["cards"]] == ["dept", "n"]
    # what the row holds: ids and enums, no key beyond the definition's
    async with container.pg_engine().connect() as connection:
        doc = (await connection.execute(text("SELECT doc FROM app.form_report_views"))).scalar_one()
    assert set(doc) <= {"_id", "created_at", "updated_at", "workspace_id", "form_id", "owner_id", "scope", "name", "definition", "revision"}
    assert "care" not in json.dumps(doc["definition"]) and "Care" not in json.dumps(doc)


@pytest.mark.parametrize(
    "body,status,code",
    [
        (definition(card("c", "bar", dimension="q:nope")), 422, "unknown_field"),
        (definition(card("c", "bar", dimension="q:why")), 422, "field_not_reportable"),
        (definition(card("c", "tile", measures=[{"agg": "avg", "field": "q:dept"}])), 422, "op_not_allowed"),
        ({"v": 1, "cards": []}, 422, "invalid_definition"),
        ({"v": 2, "cards": [card()]}, 422, "invalid_definition"),
        ({**definition(card()), "where": [{"field": "q:why", "op": "is", "value": "Ada"}]}, 422, "invalid_definition"),
    ],
)
async def test_a_view_never_stores_what_a_query_would_refuse(client, world, body, status, code):
    workspace, form, people = world
    refused = await save(client, workspace, form, body={"name": "Bad", "scope": "private", "definition": body}, user=people["viewer"])
    assert refused.status_code == status and refused.json()["code"] == code, refused.text
    assert await listed(client, workspace, form, people["viewer"]) == []


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "", "definition": DEFINITION},
        {"name": "   ", "definition": DEFINITION},
        {"name": "x" * (limits.VIEW_NAME_MAX + 1), "definition": DEFINITION},
        {"name": "tab\there", "definition": DEFINITION},
        {"name": "ok", "scope": "everyone", "definition": DEFINITION},
        {"name": "ok", "definition": DEFINITION, "answers": ["Ada"]},
        {"name": "ok"},
        {"name": 5, "definition": DEFINITION},
    ],
)
async def test_a_request_with_a_bad_name_or_a_stray_key_is_refused(client, world, payload):
    workspace, form, people = world
    refused = await save(client, workspace, form, body=payload, user=people["viewer"])
    assert refused.status_code == 422 and refused.json()["code"] == "invalid_view", refused.text
    # the message says where, never what
    assert "Ada" not in refused.text


async def test_a_name_is_used_once_per_scope_and_owner(client, world):
    workspace, form, people = world
    assert (await save(client, workspace, form, "Weekly", user=people["viewer"])).status_code == 201
    taken = await save(client, workspace, form, "weekly", user=people["viewer"])
    assert taken.status_code == 409 and taken.json()["code"] == "view_name_taken"
    # another person's private view may have the same name; so may the form's own
    assert (await save(client, workspace, form, "Weekly", user=people["viewer2"])).status_code == 201
    assert (await save(client, workspace, form, "Weekly", scope="form", user=people["editor"])).status_code == 201
    again = await save(client, workspace, form, "WEEKLY", scope="form", user=people["editor2"])
    assert again.status_code == 409
    # renaming into a taken name is refused, renaming to itself is not
    other = (await save(client, workspace, form, "Other", user=people["viewer"])).json()
    clash = await call(client, "patch", workspace, form, "/" + other["id"], user=people["viewer"], json={"revision": 1, "name": "Weekly"})
    assert clash.status_code == 409
    same = await call(client, "patch", workspace, form, "/" + other["id"], user=people["viewer"], json={"revision": 1, "name": "other"})
    assert same.status_code == 200


async def test_there_are_limits(client, world, monkeypatch):
    workspace, form, people = world
    monkeypatch.setattr(limits, "VIEWS_PRIVATE_MAX", 2)
    monkeypatch.setattr(limits, "VIEWS_FORM_MAX", 1)
    for number in range(2):
        assert (await save(client, workspace, form, f"P{number}", user=people["viewer"])).status_code == 201
    full = await save(client, workspace, form, "P2", user=people["viewer"])
    assert full.status_code == 409 and full.json()["code"] == "view_limit"
    # another person's notebook has its own room
    assert (await save(client, workspace, form, "P0", user=people["viewer2"])).status_code == 201
    assert (await save(client, workspace, form, "F0", scope="form", user=people["editor"])).status_code == 201
    assert (await save(client, workspace, form, "F1", scope="form", user=people["editor"])).status_code == 409


async def test_a_change_made_from_a_stale_copy_is_refused(client, world):
    workspace, form, people = world
    view = (await save(client, workspace, form, "One", user=people["viewer"])).json()
    url = "/" + view["id"]
    assert (await call(client, "patch", workspace, form, url, user=people["viewer"], json={"revision": 1, "name": "Two"})).status_code == 200
    stale = await call(client, "patch", workspace, form, url, user=people["viewer"], json={"revision": 1, "name": "Three"})
    assert stale.status_code == 409 and stale.json()["code"] == "view_changed"
    assert (await call(client, "get", workspace, form, url, user=people["viewer"])).json()["name"] == "Two"
    # a new definition is validated as it is saved
    bad = await call(client, "patch", workspace, form, url, user=people["viewer"], json={"revision": 2, "definition": definition(card("c", "bar", dimension="q:nope"))})
    assert bad.status_code == 422 and bad.json()["code"] == "unknown_field"
    good = await call(client, "patch", workspace, form, url, user=people["viewer"], json={"revision": 2, "definition": definition(card("t", "tile"))})
    assert good.status_code == 200 and [c["id"] for c in good.json()["definition"]["cards"]] == ["t"]
    nothing = await call(client, "patch", workspace, form, url, user=people["viewer"], json={"revision": 3})
    assert nothing.status_code == 200 and nothing.json()["revision"] == 3


async def test_a_view_belongs_to_its_form_and_workspace(client, world, workspace_1):
    from tests.app.controllers.data import testUser1

    workspace, form, people = world
    other_form = await make_form(workspace, survey_fields(), title="Other")
    view = (await save(client, workspace, form, "Mine", scope="form")).json()
    assert (await call(client, "get", workspace, other_form, "/" + view["id"])).status_code == 404
    assert (await call(client, "delete", workspace, other_form, "/" + view["id"])).status_code == 404
    foreign = await make_form(workspace_1, survey_fields(), user=testUser1)
    assert (await call(client, "get", workspace, foreign, "/" + view["id"])).status_code == 404
    assert await listed(client, workspace, other_form) == []


# ------------------------------------------------------------------ permissions


@pytest.mark.parametrize("method,tail,extra", [
    ("get", "", {}),
    ("post", "", {"json": {"name": "x", "definition": DEFINITION}}),
    ("get", "/" + "a" * 24, {}),
    ("patch", "/" + "a" * 24, {"json": {"revision": 1, "name": "x"}}),
    ("delete", "/" + "a" * 24, {}),
])
async def test_a_privacy_officer_and_a_stranger_are_refused(client, world, method, tail, extra):
    from tests.app.controllers.data import testUser1

    workspace, form, people = world
    officer = await call(client, method, workspace, form, tail, user=people["officer"], **extra)
    assert officer.status_code == 403
    stranger = await call(client, method, workspace, form, tail, user=testUser1, **extra)
    assert stranger.status_code in (403, 404)


async def test_a_restricted_form_is_a_404_to_a_member_it_is_closed_to_and_a_grant_opens_it(client, world, form_access_on):
    workspace, form, people = world
    made = (await save(client, workspace, form, "Shared", scope="form", user=people["editor"])).json()
    await restrict(workspace, form.form_id)
    closed = await call(client, "get", workspace, form, user=people["viewer"])
    ghost = type("F", (), {"form_id": "f" * 24})()
    unknown = await call(client, "get", workspace, ghost, user=people["viewer"])
    assert closed.status_code == 404 and closed.json() == unknown.json()
    assert (await call(client, "get", workspace, form, "/" + made["id"], user=people["viewer"])).status_code == 404
    await grant(workspace, form.form_id, people["viewer"].id, ROLE_VIEWER)
    assert len(await listed(client, workspace, form, people["viewer"])) == 1


async def test_every_answer_is_no_store(client, world):
    workspace, form, people = world
    made = await save(client, workspace, form, "Shared", scope="form", user=people["editor"])
    for response in (
        made,
        await call(client, "get", workspace, form),
        await call(client, "get", workspace, form, "/" + made.json()["id"]),
        await call(client, "delete", workspace, form, "/" + made.json()["id"], user=people["editor"]),
    ):
        assert response.headers["cache-control"] == "no-store"


# ----------------------------------------------------------------------- audit


async def test_what_the_form_shares_is_audited_with_ids_only_and_a_notebook_is_not(client, world):
    workspace, form, people = world
    # a person's private views: never an entry
    private = (await save(client, workspace, form, "Secret plans", user=people["viewer"])).json()
    await call(client, "patch", workspace, form, "/" + private["id"], user=people["viewer"], json={"revision": 1, "name": "Still secret"})
    await call(client, "delete", workspace, form, "/" + private["id"], user=people["viewer"])
    assert await audit_events(workspace, *REPORT_EVENTS) == []
    # a view for the form
    shared = (await save(client, workspace, form, "Quarterly board numbers", scope="form", user=people["editor"])).json()
    url = "/" + shared["id"]
    await call(client, "patch", workspace, form, url, user=people["editor2"], json={"revision": 1, "name": "Board", "definition": definition(card("t", "tile"))})
    await call(client, "patch", workspace, form, url, user=people["editor"], json={"revision": 2, "scope": "private"})
    await call(client, "patch", workspace, form, url, user=people["editor"], json={"revision": 3, "scope": "form"})
    await call(client, "delete", workspace, form, url, user=people["admin"])
    rows = await audit_events(workspace, *REPORT_EVENTS)
    assert [r.event for r in rows] == [
        REPORT_VIEW_CREATED, REPORT_VIEW_UPDATED, REPORT_VIEW_UNSHARED, REPORT_VIEW_SHARED, REPORT_VIEW_DELETED,
    ]
    assert [r.user_id for r in rows] == [people[k].id for k in ("editor", "editor2", "editor", "editor", "admin")]
    assert all(r.view_id == shared["id"] and r.form_id == form.form_id for r in rows)
    assert [r.view_scope for r in rows] == ["form", "form", "private", "form", "form"]
    assert rows[1].changed == ["name", "definition"] and rows[2].changed == ["scope"]
    # ids and enums only: no name, no definition
    dumped = json.dumps([r.model_dump(mode="json") for r in rows])
    for secret in ("Quarterly", "Board", "Secret", "dept", "q:dept"):
        assert secret not in dumped


async def test_a_change_the_audit_log_cannot_record_is_not_made(client, world, monkeypatch):
    workspace, form, people = world
    fail_audit(monkeypatch)
    refused = await save(client, workspace, form, "Shared", scope="form", user=people["editor"])
    assert refused.status_code == 503 and refused.json()["code"] == "audit_unavailable"
    assert await listed(client, workspace, form, people["editor"]) == []
    # a private view needs no entry, so it does not depend on the log
    assert (await save(client, workspace, form, "Mine", user=people["editor"])).status_code == 201


# ------------------------------------------------------------------- clean-up


async def test_a_form_takes_its_views_with_it(client, world):
    workspace, form, people = world
    other = await make_form(workspace, survey_fields(), title="Other")
    await save(client, workspace, form, "Shared", scope="form", user=people["editor"])
    await save(client, workspace, form, "Mine", user=people["viewer"])
    await save(client, workspace, other, "Keep", scope="form", user=people["editor"])
    await container.workspace_form_service().delete_form_from_workspace(workspace.id, form.form_id, testUser)
    async with container.pg_engine().connect() as connection:
        left = (await connection.execute(text("SELECT form_id FROM app.form_report_views"))).scalars().all()
    assert left == [other.form_id]


async def test_a_member_who_leaves_takes_their_private_views_and_the_form_keeps_theirs(client, world):
    workspace, form, people = world
    leaver = people["editor"]
    await save(client, workspace, form, "Private", user=leaver)
    kept = (await save(client, workspace, form, "Shared", scope="form", user=leaver)).json()
    await save(client, workspace, form, "Someone else's", user=people["viewer"])
    removed = await container.member_removal_repo().remove(workspace.id, leaver.id, testUser.id)
    assert removed is not None
    names = sorted(v["name"] for v in await listed(client, workspace, form, people["viewer"]))
    assert names == ["Shared", "Someone else's"]
    # the form's view is now a former member's: no name, still deletable by an admin
    seen = [v for v in await listed(client, workspace, form, people["admin"]) if v["id"] == kept["id"]][0]
    assert seen["ownerName"] is None and seen["mine"] is False
    assert (await call(client, "delete", workspace, form, "/" + kept["id"], user=people["admin"])).status_code == 204
