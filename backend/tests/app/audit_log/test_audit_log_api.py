"""The audit log routes (``AUDIT_LOG_UI_ENABLED``): the workspace's and a form's
entries, read only. The switch, who may read, what a Privacy officer never
gets, the keyset pages, every filter, the names ids resolve to, and nothing
reaching across workspaces. Everything here is synthetic."""

import datetime as dt
import json
from unittest.mock import AsyncMock, patch

import pytest
from common.ids import RecordId
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.dtos.audit_log_dto import AuditEntryDto
from backend.app.schemas import workspace_audit_event as E
from backend.app.schemas.workspace_audit_event import WorkspaceAuditEventDocument
from backend.app.services.audit_log.mode import OFF_CODE
from backend.app.services.audit_log.retention import DAYS_OF_MONTHS
from backend.config import settings
from tests.app.controllers.data import testUser, testUser1
from tests.app.form_access.helpers import (
    add_member,
    api,
    cookies,
    create_form,
    grant,
    restrict,
    team_with,
)
from tests.app.form_access.test_switch_and_memo import statements

pytestmark = pytest.mark.asyncio

BASE = dt.datetime(2026, 10, 1, 8, 0, tzinfo=dt.timezone.utc)
SESSION = "sid-secret-0001"


@pytest.fixture(autouse=True)
def switched_on(monkeypatch):
    monkeypatch.setattr(settings, "AUDIT_LOG_UI_ENABLED", True)


@pytest.fixture(autouse=True)
def auth_service():
    """The auth service answers every id it is asked for with a name and an
    address (the address must never reach the page)."""

    async def get(url, **kwargs):
        ids = [str(i) for i in (kwargs.get("params") or {}).get("user_ids", [])]
        return {
            "users_info": [
                {
                    "_id": i,
                    "first_name": "Name",
                    "last_name": i[-6:],
                    "email": f"{i}@mail.voorbeeld.example",
                }
                for i in ids
            ]
        }

    with patch("common.services.http_client.HttpClient.get", AsyncMock(side_effect=get)) as m:
        yield m


async def seed(workspace, event, minutes=0, user_id=None, **fields) -> WorkspaceAuditEventDocument:
    document = WorkspaceAuditEventDocument(
        id=RecordId(),
        workspace_id=workspace.id,
        user_id=user_id if user_id is not None else testUser.id,
        session_id=fields.pop("session_id", SESSION),
        event=event,
        created_at=BASE + dt.timedelta(minutes=minutes),
        **fields,
    )
    await container.workspace_audit_repo().record(document)
    return document


def audit_url(workspace, form=None) -> str:
    return api(workspace) + (f"/forms/{form}/audit-log" if form else "/audit-log")


async def read(client, workspace, user=testUser, form=None, **params):
    return await client.get(
        audit_url(workspace, form), cookies=cookies(user), params=params
    )


def ids(response):
    return [e["id"] for e in response.json()["entries"]]


# -- the switch -------------------------------------------------------------------
async def test_both_routes_answer_422_and_read_nothing_while_the_switch_is_off(
    client: AsyncClient, workspace, workspace_form, monkeypatch
):
    monkeypatch.setattr(settings, "AUDIT_LOG_UI_ENABLED", False)
    await seed(workspace, E.ACCESS_MODE_CHANGED, form_id=workspace_form.form_id)
    with statements() as seen:
        one = await read(client, workspace)
        two = await read(client, workspace, form=workspace_form.form_id)
        # not even for someone who may not read: the switch decides first
        three = await read(client, workspace, user=testUser1)
    for response in (one, two, three):
        assert response.status_code == 422, response.text
        assert response.json()["code"] == OFF_CODE
    assert seen == [] or not any("workspace_audit_events" in s for s in seen)


async def test_the_switch_is_off_by_default_and_the_permissions_say_whether_it_is_on(
    client: AsyncClient, workspace, monkeypatch
):
    from backend.config.application import Application

    assert Application.model_fields["AUDIT_LOG_UI_ENABLED"].default is False
    for enabled in (True, False):
        monkeypatch.setattr(settings, "AUDIT_LOG_UI_ENABLED", enabled)
        response = await client.get(
            f"{api(workspace)}/permissions", cookies=cookies(testUser)
        )
        assert response.status_code == 200, response.text
        assert response.json()["auditLogUiEnabled"] is enabled


# -- who may read ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "roles,status",
    [
        (["ADMIN"], 200),
        (["OWNER"], 200),
        (["PRIVACY_OFFICER"], 200),
        (["COLLABORATOR"], 403),
        (["EDITOR"], 403),
        (["REVIEWER"], 403),
        (["VIEWER"], 403),
        ([], 403),
    ],
)
async def test_only_audit_read_opens_either_route(
    client: AsyncClient, workspace, workspace_form, roles, status
):
    member = await add_member(workspace, *roles)
    await seed(workspace, E.ACCESS_MODE_CHANGED, form_id=workspace_form.form_id)
    for form in (None, workspace_form.form_id):
        response = await read(client, workspace, member, form=form)
        assert response.status_code == status, (form, response.text)
        if status == 403:
            assert "entries" not in response.text


async def test_strangers_and_the_signed_out_are_refused(
    client: AsyncClient, workspace, workspace_form
):
    for form in (None, workspace_form.form_id):
        # a user of no workspace, and a disabled member
        assert (await read(client, workspace, testUser1, form=form)).status_code == 403
        disabled = await add_member(workspace, "ADMIN", disabled=True)
        assert (await read(client, workspace, disabled, form=form)).status_code == 403
        assert (await client.get(audit_url(workspace, form))).status_code == 401


# -- pages ------------------------------------------------------------------------------
async def test_keyset_pages_are_complete_ordered_and_stable_with_ties_and_new_rows(
    client: AsyncClient, workspace
):
    # 45 entries, three to a minute: the cursor has to break ties by id
    seeded = [
        await seed(workspace, E.ACCESS_MODE_CHANGED, minutes=i // 3, access_mode="restricted")
        for i in range(45)
    ]
    expected = [
        str(d.id)
        for d in sorted(seeded, key=lambda d: (d.created_at, str(d.id)), reverse=True)
    ]

    first = await read(client, workspace)
    assert first.status_code == 200, first.text
    assert len(first.json()["entries"]) == 20 and first.json()["nextCursor"]

    # newer entries arriving between two requests do not move the older pages
    await seed(workspace, E.ACCESS_MODE_CHANGED, minutes=500)
    second = await read(client, workspace, cursor=first.json()["nextCursor"])
    third = await read(client, workspace, cursor=second.json()["nextCursor"])
    walked = ids(first) + ids(second) + ids(third)
    assert walked == expected
    assert len(ids(third)) == 5 and third.json()["nextCursor"] is None
    # an exact multiple of the limit ends without an empty extra page
    exact = await read(client, workspace, limit=46)
    assert len(ids(exact)) == 46 and exact.json()["nextCursor"] is None


async def test_the_page_size_defaults_to_20_and_is_at_most_100(
    client: AsyncClient, workspace
):
    for i in range(105):
        await seed(workspace, E.ACCESS_MODE_CHANGED, minutes=i)
    assert len(ids(await read(client, workspace))) == 20
    hundred = await read(client, workspace, limit=100)
    assert len(ids(hundred)) == 100 and hundred.json()["nextCursor"]
    for bad in (0, 101, -1):
        assert (await read(client, workspace, limit=bad)).status_code == 422


@pytest.mark.parametrize("cursor", ["x", "!!!", "e" * 201, "MjAyNi1ub3QtYS1kYXRlfGFiYw"])
async def test_a_cursor_that_is_not_one_is_422(client: AsyncClient, workspace, cursor):
    response = await read(client, workspace, cursor=cursor)
    assert response.status_code == 422, response.text


# -- filters --------------------------------------------------------------------------------
async def test_each_filter_narrows_and_they_combine(
    client: AsyncClient, workspace, workspace_form
):
    form, other_form = workspace_form.form_id, str(RecordId())
    alice, bob, carol = [await add_member(workspace, "ADMIN") for _ in range(3)]
    team = await team_with(workspace, bob, name="Planners")
    grant_a = await seed(
        workspace, E.ACCESS_GRANT_ADDED, 1, user_id=alice.id, form_id=form,
        target_user_id=bob.id, grant_role="VIEWER",
    )
    mode_b = await seed(
        workspace, E.ACCESS_MODE_CHANGED, 2, user_id=bob.id, form_id=other_form,
        access_mode="restricted",
    )
    removed = await seed(
        workspace, E.MEMBER_REMOVED, 3, user_id=alice.id, target_user_id=carol.id
    )
    team_c = await seed(
        workspace, E.TEAM_CREATED, 4, user_id=carol.id, group_id=str(team.id)
    )
    sso = await seed(workspace, E.SSO_BREAK_GLASS_SIGN_IN, 5, user_id=carol.id)
    key = await seed(workspace, E.API_KEY_CREATED, 6, user_id=alice.id, key_id="k1")
    docs = [grant_a, mode_b, removed, team_c, sso, key]
    name = {str(d.id): i for i, d in enumerate(docs)}

    async def which(**params):
        response = await read(client, workspace, **params)
        assert response.status_code == 200, (params, response.text)
        return sorted(name[i] for i in ids(response))

    assert await which() == [0, 1, 2, 3, 4, 5]
    # area, event, and both together (the union of what they name)
    assert await which(area="access") == [0, 1, 3]
    assert await which(area=["members", "api_keys"]) == [2, 5]
    assert await which(event="member_removed") == [2]
    assert await which(area="security", event="team_created") == [3, 4]
    # who: the actor, the one it was done to, either
    assert await which(actor=alice.id) == [0, 2, 5]
    assert await which(target=bob.id) == [0]
    assert await which(target=carol.id) == [2]
    assert await which(involving=bob.id) == [0, 1]
    assert await which(involving=carol.id) == [2, 3, 4]
    # a form
    assert await which(form_id=form) == [0]
    assert await which(form_id=other_form) == [1]
    # a range of time, both ends inclusive
    assert await which(**{"from": (BASE + dt.timedelta(minutes=2)).isoformat()}) == [1, 2, 3, 4, 5]
    assert await which(**{"to": (BASE + dt.timedelta(minutes=2)).isoformat()}) == [0, 1]
    assert await which(
        **{
            "from": (BASE + dt.timedelta(minutes=2)).isoformat(),
            "to": (BASE + dt.timedelta(minutes=4)).isoformat(),
        }
    ) == [1, 2, 3]
    # combined
    assert await which(actor=alice.id, area="access") == [0]
    assert await which(actor=alice.id, form_id=other_form) == []
    # a filter that matches nothing is an empty page, not an error
    assert await which(actor="nobody") == []

    # the form's own feed is the same filter with the form fixed
    one = await read(client, workspace, form=form)
    assert [name[i] for i in ids(one)] == [0]
    assert ids(await read(client, workspace, form=form, actor=bob.id)) == []


@pytest.mark.parametrize(
    "params",
    [
        {"area": "nonsense"},
        {"event": "totp_enrolled"},  # a kind of the schema that no workspace feed lists
        {"event": "no_such_event"},
        {"actor": "a b"},
        {"actor": "x" * 129},
        {"form_id": "../etc"},
        {"involving": "'; drop table"},
        {"from": "yesterday"},
        {"from": "2026-10-02T00:00:00Z", "to": "2026-10-01T00:00:00Z"},
    ],
)
async def test_a_filter_that_is_not_valid_is_422(client: AsyncClient, workspace, params):
    response = await read(client, workspace, **params)
    assert response.status_code == 422, (params, response.text)


async def test_only_listed_kinds_of_this_workspace_come_back(
    client: AsyncClient, workspace, workspace_1
):
    mine = await seed(workspace, E.ACCESS_MODE_CHANGED, 1)
    # a second-factor event of one account, even stamped with this workspace
    await seed(workspace, E.TOTP_ENROLLED, 2)
    await seed(workspace, "some_future_kind", 3)
    await seed(workspace_1, E.ACCESS_MODE_CHANGED, 4)
    response = await read(client, workspace)
    assert ids(response) == [str(mine.id)]


# -- the entry and what it never holds ---------------------------------------------------
async def test_an_entry_is_the_dto_and_nothing_else(client: AsyncClient, workspace):
    await seed(
        workspace, E.ACCESS_GRANT_ADDED, 1, form_id="f1", target_user_id="u2",
        group_id="g1", grant_role="EDITOR", grant_export=True,
    )
    entry = (await read(client, workspace)).json()["entries"][0]
    from fastapi_camelcase import CamelModel

    camel = {CamelModel.model_config["alias_generator"](n) for n in AuditEntryDto.model_fields}
    assert set(entry) <= camel
    assert entry["event"] == E.ACCESS_GRANT_ADDED and entry["area"] == "access"
    assert (entry["grantRole"], entry["grantExport"], entry["formId"]) == ("EDITOR", True, "f1")


async def test_a_team_link_entry_says_linked_or_unlinked_and_which_directory_group(
    client: AsyncClient, workspace
):
    await seed(
        workspace, E.TEAM_LINKED, 1, group_id="g1", scim_group_id="d1", linked=True
    )
    await seed(
        workspace, E.TEAM_LINKED, 2, group_id="g1", scim_group_id="d1", linked=False
    )
    entries = (await read(client, workspace)).json()["entries"]
    assert [(e["event"], e["linked"], e["groupId"]) for e in entries] == [
        (E.TEAM_LINKED, False, "g1"),
        (E.TEAM_LINKED, True, "g1"),
    ]
    assert {e["scimGroupId"] for e in entries} == {"d1"}


def test_every_field_of_a_stored_entry_is_returned_or_withheld_on_purpose():
    """A field added to the schema has to be decided here: shown (it is in the
    DTO) or kept back. So a new field never reaches a page by being copied."""
    shown = {
        "id", "created_at", "event", "session_id", "target_user_id", "to_user_id",
        "form_id", "response_id", "revision", "group_id", "grant_role", "grant_export",
        "access_mode", "linked", "scim_group_id", "role", "previous_role", "count", "required", "export_channel",
        "export_format", "key_id", "reason", "key_role", "key_role_before", "form_scope",
        "widened", "method", "path", "connection_type", "directory_type", "enabled",
        "provider", "changed", "retention_months", "previous_retention_months",
    }
    # actor_id is user_id; at is created_at
    withheld = {
        "workspace_id",  # the path says it
        "user_id",  # returned as actor_id
        "updated_at",
        "invitation_id",  # an invitation has no screen
        "export_id",  # a pointer to a row the page cannot open
        # ids of settings and integrations that have no screen of their own
        "connection_id", "domain_id", "directory_id", "directory_group_id",
        "action_id", "service_id",
        # the other side of a copy of a form to another workspace: that workspace's
        # ids are no business of this workspace's readers (a Privacy officer need
        # not be a member of the other one)
        "source_workspace_id",
        "source_form_id",
        "target_workspace_id",
        "target_form_id",
    }
    dto = {n for n in AuditEntryDto.model_fields}
    stored = set(WorkspaceAuditEventDocument.model_fields)
    assert stored == shown | withheld, stored ^ (shown | withheld)
    missing = {f for f in shown if f not in dto and f not in {"id", "created_at"}}
    assert not missing, missing


async def test_names_are_current_members_only_and_a_member_who_left_has_no_name(
    client: AsyncClient, workspace, workspace_form, auth_service
):
    present = await add_member(workspace, "VIEWER")
    gone = str(RecordId())  # held a membership once, has none now
    left_team = str(RecordId())
    team = await team_with(workspace, present, name="Planners")
    await seed(
        workspace, E.TEAM_MEMBER_ADDED, 1, user_id=testUser.id, target_user_id=present.id,
        group_id=str(team.id),
    )
    await seed(
        workspace, E.MEMBER_REMOVED, 2, user_id=gone, target_user_id=present.id,
        form_id=workspace_form.form_id,
    )
    await seed(workspace, E.TEAM_DELETED, 3, user_id=testUser.id, group_id=left_team)
    deleted_form = str(RecordId())
    await seed(workspace, E.ACCESS_MODE_CHANGED, 4, form_id=deleted_form)

    response = await read(client, workspace)
    body = response.json()
    labels = body["labels"]
    assert labels["members"][present.id] == {"status": "member", "name": f"Name {present.id[-6:]}"}
    # who left: no name at all, though the auth service would have one
    assert labels["members"][gone] == {"status": "former", "name": None}
    assert gone[-6:] not in response.text.replace(gone, "")
    assert labels["forms"][workspace_form.form_id]["status"] == "available"
    assert labels["forms"][workspace_form.form_id]["title"] == workspace_form.title
    assert labels["forms"][deleted_form] == {"status": "gone", "title": None}
    assert labels["teams"][str(team.id)] == {"status": "available", "name": "Planners"}
    assert labels["teams"][left_team] == {"status": "gone", "name": None}
    # the auth service was asked about current members only
    asked = [c.kwargs["params"]["user_ids"] for c in auth_service.call_args_list]
    assert all(gone not in a for a in asked)
    # and never an address on the page
    assert "mail.voorbeeld.example" not in response.text
    assert body["retentionDays"] == 365


async def test_a_failed_name_lookup_leaves_the_page_without_names(
    client: AsyncClient, workspace
):
    member = await add_member(workspace, "VIEWER")
    await seed(workspace, E.MEMBER_ROLE_CHANGED, 1, target_user_id=member.id, role="VIEWER")
    with patch(
        "common.services.http_client.HttpClient.get",
        AsyncMock(side_effect=ConnectionError("down")),
    ):
        response = await read(client, workspace)
    assert response.status_code == 200
    assert response.json()["labels"]["members"][member.id] == {"status": "member", "name": None}


async def test_the_retention_comes_from_one_place_not_from_the_page(
    client: AsyncClient, workspace, monkeypatch
):
    assert (await read(client, workspace)).json()["retentionDays"] == DAYS_OF_MONTHS[12]

    async def six_months(workspace_id):
        return 183

    monkeypatch.setattr(container.audit_retention(), "days", six_months)
    assert (await read(client, workspace)).json()["retentionDays"] == 183


# -- the Privacy officer and the others -----------------------------------------------------
async def test_a_privacy_officer_sees_who_did_what_but_no_response_link_and_no_session(
    client: AsyncClient, workspace, workspace_form, monkeypatch
):
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    form = workspace_form.form_id
    await restrict(workspace, form)
    officer = await add_member(workspace, "PRIVACY_OFFICER")
    admin = await add_member(workspace, "ADMIN")
    await seed(workspace, E.ACCESS_GRANT_ADDED, 1, form_id=form, target_user_id=admin.id, grant_role="VIEWER")
    response_id = str(RecordId())
    await seed(
        workspace, E.RESPONSE_REVISION_READ, 2, user_id=admin.id, form_id=form,
        response_id=response_id, revision=3,
    )

    for who, link, session in ((testUser, True, True), (admin, True, True), (officer, False, False)):
        for form_feed in (None, form):
            response = await read(client, workspace, who, form=form_feed)
            assert response.status_code == 200, (who.id, response.text)
            entries = response.json()["entries"]
            assert [e["event"] for e in entries] == [E.RESPONSE_REVISION_READ, E.ACCESS_GRANT_ADDED]
            read_entry = entries[0]
            assert (read_entry["responseId"] == response_id) is link, who.id
            assert (read_entry["sessionId"] == SESSION) is session, who.id
            if not link:
                assert response_id not in response.text
            if not session:
                assert SESSION not in response.text
            # the event itself (who, which form, which entry) is still there
            assert read_entry["actorId"] == admin.id and read_entry["formId"] == form
            assert read_entry["revision"] == 3
            assert "mail.voorbeeld.example" not in response.text


async def test_a_grantee_editor_does_not_see_a_forms_access_activity(
    client: AsyncClient, workspace, workspace_form, monkeypatch
):
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    form = workspace_form.form_id
    await restrict(workspace, form)
    editor = await add_member(workspace, "EDITOR")
    viewer = await add_member(workspace, "VIEWER")
    await grant(workspace, form, editor.id, "EDITOR")
    await grant(workspace, form, viewer.id, "EDITOR")
    await seed(workspace, E.ACCESS_GRANT_ADDED, 1, form_id=form, target_user_id=editor.id)
    for member in (editor, viewer):
        assert (await read(client, workspace, member, form=form)).status_code == 403
        assert (await read(client, workspace, member)).status_code == 403


async def test_a_restricted_form_is_a_404_for_nobody_who_holds_audit_read(
    client: AsyncClient, workspace, workspace_form, monkeypatch
):
    """A Privacy officer holds no grant on the restricted form and still reads
    its feed (their accountability job); a member the form is closed to and
    whose role lacks audit.read is refused (403) like every other member."""
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    form = workspace_form.form_id
    await restrict(workspace, form)
    officer = await add_member(workspace, "PRIVACY_OFFICER")
    reviewer = await add_member(workspace, "REVIEWER")
    assert (await read(client, workspace, officer, form=form)).status_code == 200
    assert (await read(client, workspace, reviewer, form=form)).status_code in (403, 404)


# -- other workspaces ----------------------------------------------------------------------
async def test_nothing_crosses_workspaces(
    client: AsyncClient, workspace, workspace_1, workspace_form, workspace_form_1
):
    mine = await seed(workspace, E.ACCESS_MODE_CHANGED, 1, form_id=workspace_form.form_id)
    theirs = await seed(
        workspace_1, E.ACCESS_MODE_CHANGED, 2, user_id=testUser1.id,
        form_id=workspace_form_1.form_id,
    )
    other_team = await team_with(workspace_1, name="Their team")
    await seed(workspace, E.TEAM_RENAMED, 3, group_id=str(other_team.id))
    await seed(workspace, E.ACCESS_MODE_CHANGED, 4, form_id=workspace_form_1.form_id)

    # each owner reads their own
    assert str(theirs.id) in ids(await read(client, workspace_1, testUser1))
    assert str(theirs.id) not in ids(await read(client, workspace))

    # another workspace's id in the path: 403 (not a member), no entries
    foreign = await read(client, workspace_1, testUser)
    assert foreign.status_code == 403 and "entries" not in foreign.text
    # another workspace's form in the path or as a filter: 404 / nothing
    other_form = workspace_form_1.form_id
    assert (await read(client, workspace, form=other_form)).status_code == 404
    assert str(theirs.id) not in ids(await read(client, workspace, form_id=other_form))

    # ids that point into another workspace resolve to nothing there
    body = (await read(client, workspace)).json()
    assert body["labels"]["forms"][other_form] == {"status": "gone", "title": None}
    assert body["labels"]["teams"][str(other_team.id)] == {"status": "gone", "name": None}
    assert "Their team" not in json.dumps(body)
    # a form feed answers with this workspace's rows of the form only
    assert ids(await read(client, workspace, form=workspace_form.form_id)) == [str(mine.id)]


# -- cost ---------------------------------------------------------------------------------------
async def test_the_number_of_queries_of_a_page_does_not_grow_with_its_entries(
    client: AsyncClient, workspace, workspace_form, monkeypatch
):
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    people = [await add_member(workspace, "VIEWER") for _ in range(6)]
    team = await team_with(workspace, *people[:2])
    await seed(
        workspace, E.TEAM_MEMBER_ADDED, 0, target_user_id=people[0].id,
        group_id=str(team.id), form_id=workspace_form.form_id,
    )
    with statements() as small:
        assert (await read(client, workspace)).status_code == 200

    forms = [(await create_form(workspace, testUser)).form_id for _ in range(4)]
    for i in range(60):
        await seed(
            workspace, E.RESPONSE_REVISION_READ, i + 1, user_id=people[i % 6].id,
            target_user_id=people[(i + 1) % 6].id, form_id=forms[i % 4],
            response_id=str(RecordId()), group_id=str(team.id), revision=i,
        )
    with statements() as big:
        response = await read(client, workspace, limit=50)
    assert response.status_code == 200 and len(ids(response)) == 50
    assert len(big) <= len(small) + 2, (len(small), len(big))
    assert len(big) < 40
    # and a form's feed
    with statements() as one_form:
        assert (await read(client, workspace, form=forms[0])).status_code == 200
    assert len(one_form) < 40


async def test_reading_the_log_writes_nothing(client: AsyncClient, workspace, workspace_form):
    await seed(workspace, E.ACCESS_MODE_CHANGED, 1, form_id=workspace_form.form_id)
    before = await container.workspace_audit_repo().page(workspace.id, 100)
    with statements() as seen:
        await read(client, workspace)
        await read(client, workspace, form=workspace_form.form_id)
    assert not [s for s in seen if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]
    assert len(await container.workspace_audit_repo().page(workspace.id, 100)) == len(before)
