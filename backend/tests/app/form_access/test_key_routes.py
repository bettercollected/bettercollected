"""The routes that give an API key a role and a list of forms (create, list,
edit, revoke), behind ``API_KEY_ROLES_ENABLED``: the role and scope matrix, the
widening rule, the audit entries (stored before the change), the key's rows
going with a revocation, and the switch. Everything here is synthetic."""

import pytest
from common.ids import RecordId
from httpx import AsyncClient

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.schemas.form_access_grant import SUBJECT_KEY
from backend.app.schemas.workspace_audit_event import (
    API_KEY_CREATED,
    API_KEY_EVENTS,
    API_KEY_FORM_ADDED,
    API_KEY_FORM_REMOVED,
    API_KEY_REVOKED,
    API_KEY_ROLE_CHANGED,
    API_KEY_SCOPE_CHANGED,
    REVOKED_BY_ADMIN,
    REVOKED_WORKSPACE_DELETED,
)
from backend.app.services.ai.api_keys import _hash
from backend.config import settings
from tests.app.controllers.data import testUser, testUser1
from tests.app.form_access.helpers import (
    add_member,
    api,
    audit_events,
    cookies,
    create_form,
    fail_audit,
)
from tests.app.form_access.test_key_roles import (
    admin_creator,
    make_key,
    roles_off,  # noqa: F401
    roles_on,  # noqa: F401
)

pytestmark = pytest.mark.asyncio

NAME = "nightly-export-key"
READ = ["forms:read"]


def keys_url(workspace, key_id=None) -> str:
    return f"{api(workspace)}/api-keys" + (f"/{key_id}" if key_id else "")


async def create(client, workspace, user=testUser, **body):
    body = {"name": NAME, "scopes": READ, **body}
    return await client.post(keys_url(workspace), json=body, cookies=cookies(user))


async def patch(client, workspace, key_id, user=testUser, **body):
    return await client.patch(
        keys_url(workspace, key_id), json=body, cookies=cookies(user)
    )


async def rows_of(workspace, key_id):
    return sorted(
        str(r.form_id)
        for r in await container.form_access_grant_repo().for_key(workspace.id, key_id)
    )


async def stored(key_id):
    return await container.workspace_api_key_repo().get_or_404(RecordId(str(key_id)))


def code(response) -> str:
    return response.json().get("code")


@pytest.fixture()
async def forms(workspace):
    return [await create_form(workspace, testUser) for _ in range(3)]


def ids(forms):
    return [str(f.form_id) for f in forms]


# =========================================================================== the switch
async def test_with_the_switch_off_a_role_or_a_list_is_refused(
    client: AsyncClient, workspace, forms, roles_off
):
    for body in (
        {"role": "VIEWER"},
        {"formScope": "listed", "formIds": ids(forms)[:1]},
        {"role": "EDITOR", "formScope": "listed", "formIds": []},
    ):
        refused = await create(client, workspace, **body)
        assert refused.status_code == 422, refused.text
        assert code(refused) == "api_key_roles_off"
    assert await container.workspace_api_key_repo().list_by_workspace(workspace.id) == []


async def test_with_the_switch_off_a_plain_key_is_as_it_always_was(
    client: AsyncClient, workspace, roles_off
):
    for body in ({}, {"role": None}, {"formScope": "all"}):
        made = await create(client, workspace, **body)
        assert made.status_code == 200, made.text
        assert made.json()["role"] is None and made.json()["formScope"] == "all"
        assert made.json()["forms"] == []
        row = await stored(made.json()["id"])
        assert (row.role, row.form_scope) == (None, "all")


async def test_the_edit_route_answers_422_while_the_switch_is_off(
    client: AsyncClient, workspace, roles_off
):
    made = (await create(client, workspace)).json()
    refused = await patch(client, workspace, made["id"], role="VIEWER")
    assert refused.status_code == 422 and code(refused) == "api_key_roles_off"
    assert (await stored(made["id"])).role is None
    # a body that names nothing is refused the same way
    assert (await patch(client, workspace, made["id"])).status_code == 422


async def test_the_permissions_say_whether_roles_are_on(
    client: AsyncClient, workspace, monkeypatch
):
    url = f"{api(workspace)}/permissions"
    for on in (False, True):
        monkeypatch.setattr(settings.api_key_roles, "ENABLED", on)
        body = (await client.get(url, cookies=cookies(testUser))).json()
        assert body["apiKeyRolesEnabled"] is on


async def test_a_limit_stored_while_on_is_listed_after_the_switch_goes_off(
    client: AsyncClient, workspace, forms, monkeypatch
):
    monkeypatch.setattr(settings.api_key_roles, "ENABLED", True)
    made = (
        await create(
            client, workspace, role="VIEWER", formScope="listed", formIds=ids(forms)[:1]
        )
    ).json()
    monkeypatch.setattr(settings.api_key_roles, "ENABLED", False)
    listed = (await client.get(keys_url(workspace), cookies=cookies(testUser))).json()
    assert [(k["role"], k["formScope"], [f["id"] for f in k["forms"]]) for k in listed] == [
        ("VIEWER", "listed", ids(forms)[:1])
    ]
    # revoking works whatever the switch says
    revoked = await client.delete(keys_url(workspace, made["id"]), cookies=cookies(testUser))
    assert revoked.status_code == 200
    assert await rows_of(workspace, made["id"]) == []


# =========================================================================== create
async def test_a_key_is_created_with_a_role_and_a_list(
    client: AsyncClient, workspace, forms, roles_on
):
    made = await create(
        client,
        workspace,
        role="reviewer",
        scopes=["forms:read", "responses:read"],
        acknowledgeUnredactedResponses=True,
        formScope="listed",
        formIds=ids(forms)[:2] + ids(forms)[:1],
    )
    assert made.status_code == 200, made.text
    body = made.json()
    assert body["role"] == "REVIEWER" and body["formScope"] == "listed"
    assert {f["id"] for f in body["forms"]} == set(ids(forms)[:2])
    assert all(f["title"] for f in body["forms"])
    assert body["token"].startswith("bc_")
    assert await rows_of(workspace, body["id"]) == sorted(ids(forms)[:2])
    row = (await container.form_access_grant_repo().for_key(workspace.id, body["id"]))[0]
    assert (row.subject_type, row.role) == (SUBJECT_KEY, "REVIEWER")
    # the list shows the same and never the token
    listed = (await client.get(keys_url(workspace), cookies=cookies(testUser))).json()
    assert len(listed) == 1 and "token" not in listed[0]
    assert {f["id"] for f in listed[0]["forms"]} == set(ids(forms)[:2])


async def test_an_unlimited_key_made_with_the_switch_on_lists_no_forms(
    client: AsyncClient, workspace, roles_on
):
    body = (await create(client, workspace)).json()
    assert (body["role"], body["formScope"], body["forms"]) == (None, "all", [])


@pytest.mark.parametrize(
    "role,scopes,expected",
    [
        ("REVIEWER", ["forms:write"], "scope_not_allowed_by_role"),
        ("VIEWER", ["forms:delete"], "scope_not_allowed_by_role"),
        ("VIEWER", ["forms:read", "deletion_requests:read"], "scope_not_allowed_by_role"),
        ("EDITOR", ["deletion_requests:write"], "scope_not_allowed_by_role"),
        ("PRIVACY_OFFICER", ["responses:read"], "scope_not_allowed_by_role"),
        ("PRIVACY_OFFICER", ["forms:write"], "scope_not_allowed_by_role"),
    ],
)
async def test_a_role_cannot_carry_a_scope_it_does_not_hold(
    client: AsyncClient, workspace, roles_on, role, scopes, expected
):
    refused = await create(
        client,
        workspace,
        role=role,
        scopes=scopes,
        acknowledgeUnredactedResponses=True,
    )
    assert refused.status_code == 400, refused.text
    assert code(refused) == expected
    # it names the scope and nothing else of the request
    assert any(s in refused.json()["message"] for s in scopes)


@pytest.mark.parametrize(
    "role,scopes",
    [
        ("EDITOR", ["forms:read", "forms:write", "responses:read"]),
        ("REVIEWER", ["forms:read", "responses:read"]),
        ("VIEWER", ["forms:read", "responses:read"]),
        ("PRIVACY_OFFICER", ["forms:read", "deletion_requests:read", "deletion_requests:write"]),
        ("EDITOR", ["forms:delete"]),
    ],
)
async def test_a_role_carries_the_scopes_it_holds(
    client: AsyncClient, workspace, roles_on, role, scopes
):
    made = await create(
        client,
        workspace,
        role=role,
        scopes=scopes,
        acknowledgeUnredactedResponses=True,
    )
    assert made.status_code == 200, made.text


@pytest.mark.parametrize(
    "scopes",
    [["forms:delete"], ["forms:read", "deletion_requests:read"], ["deletion_requests:write"]],
)
async def test_a_listed_key_never_carries_delete_or_deletion_requests(
    client: AsyncClient, workspace, forms, roles_on, scopes
):
    for role in (None, "EDITOR"):
        refused = await create(
            client,
            workspace,
            role=role,
            scopes=scopes,
            formScope="listed",
            formIds=ids(forms)[:1],
        )
        assert refused.status_code == 400, refused.text
        assert code(refused) == "scope_not_allowed_for_listed_key"
    # the same scopes are fine on a key that is not limited to forms
    assert (await create(client, workspace, scopes=scopes)).status_code == 200


async def test_the_form_list_is_checked(
    client: AsyncClient, workspace, forms, roles_on
):
    foreign = await create_form(
        await _other_workspace(), testUser1
    )
    bad = {
        "a form of another workspace": [str(foreign.form_id)],
        "a form that is not there": [str(RecordId())],
        "not an id": ["not-an-id"],
    }
    answers = {}
    for what, form_ids in bad.items():
        refused = await create(client, workspace, formScope="listed", formIds=form_ids)
        assert refused.status_code == 400, (what, refused.text)
        answers[what] = (refused.status_code, refused.text)
    # one answer for a form of someone else's workspace and one that is not there
    assert answers["a form of another workspace"] == answers["a form that is not there"]
    # formIds needs a listed scope, and a listed scope needs formIds
    refused = await create(client, workspace, formIds=ids(forms)[:1])
    assert refused.status_code == 400 and code(refused) == "form_ids_need_listed_scope"
    refused = await create(client, workspace, formScope="listed")
    assert refused.status_code == 400 and code(refused) == "form_ids_required"
    # an empty list is a key that opens nothing
    empty = await create(client, workspace, formScope="listed", formIds=[])
    assert empty.status_code == 200 and empty.json()["forms"] == []
    # a role and a scope this code does not know
    refused = await create(client, workspace, role="OWNER")
    assert refused.status_code == 400 and code(refused) == "invalid_key_role"
    refused = await create(client, workspace, role="ADMIN")
    assert code(refused) == "invalid_key_role"
    refused = await create(client, workspace, formScope="some")
    assert refused.status_code == 400 and code(refused) == "invalid_form_scope"
    assert len(await container.workspace_api_key_repo().list_by_workspace(workspace.id)) == 1


async def _other_workspace():
    from tests.app.controllers.test_api_keys import TestAPIKeys  # noqa: F401
    from backend.app.services import workspace_service

    await workspace_service.create_workspace(testUser1)
    return await container.workspace_repo().get_default_workspace_by_owner_id(testUser1.id)


async def test_submission_forms_must_be_on_the_list(
    client: AsyncClient, workspace, forms, roles_on, monkeypatch
):
    monkeypatch.setattr(settings, "SUBMISSIONS_API_ENABLED", True)
    refused = await create(
        client,
        workspace,
        scopes=["submissions:write"],
        formScope="listed",
        formIds=ids(forms)[:1],
        submissionFormIds=ids(forms)[1:2],
    )
    assert refused.status_code == 400, refused.text
    assert code(refused) == "submission_form_outside_list"
    ok = await create(
        client,
        workspace,
        scopes=["submissions:write"],
        formScope="listed",
        formIds=ids(forms)[:2],
        submissionFormIds=ids(forms)[1:2],
    )
    assert ok.status_code == 200, ok.text


async def test_a_key_cannot_have_a_role_above_the_person_who_makes_it(
    workspace, roles_on
):
    editor = await add_member(workspace, "COLLABORATOR")
    service = container.api_key_service()
    for role in ("PRIVACY_OFFICER",):
        with pytest.raises(HTTPException) as refused:
            await service._require_within_creator(workspace.id, editor, role, READ)
        assert refused.value.status_code == 403
        assert refused.value.content["code"] == "key_role_exceeds_creator"
    # a role the person holds is fine, and no role is "as its creator"
    await service._require_within_creator(workspace.id, editor, "REVIEWER", READ)
    await service._require_within_creator(workspace.id, editor, None, READ)


async def test_only_security_managers_make_edit_or_revoke_keys(
    client: AsyncClient, workspace, forms, roles_on
):
    made = (await create(client, workspace)).json()
    for role in ("COLLABORATOR", "REVIEWER", "VIEWER", "PRIVACY_OFFICER"):
        person = await add_member(workspace, role)
        assert (await create(client, workspace, person, role="VIEWER")).status_code == 403
        assert (await patch(client, workspace, made["id"], person, role="VIEWER")).status_code == 403
        revoke = await client.delete(
            keys_url(workspace, made["id"]), cookies=cookies(person)
        )
        assert revoke.status_code == 403
    assert (await stored(made["id"])).revoked is False and (await stored(made["id"])).role is None


# =========================================================================== audit
async def test_create_and_revoke_are_audited_with_ids_only_even_with_the_switch_off(
    client: AsyncClient, workspace, roles_off
):
    made = (await create(client, workspace)).json()
    created = await audit_events(workspace, API_KEY_CREATED)
    assert [(e.key_id, e.form_scope, e.count) for e in created] == [(made["id"], "all", 0)]
    assert created[0].user_id == str(testUser.id)
    revoked = await client.delete(keys_url(workspace, made["id"]), cookies=cookies(testUser))
    assert revoked.status_code == 200
    entries = await audit_events(workspace, API_KEY_REVOKED)
    assert [(e.key_id, e.reason) for e in entries] == [(made["id"], REVOKED_BY_ADMIN)]
    # nothing of the key but its id: not its name, its prefix or its token
    everything = " ".join(
        e.model_dump_json() for e in await audit_events(workspace, *API_KEY_EVENTS)
    )
    for secret in (NAME, made["prefix"], made["token"], _hash(made["token"])):
        assert secret not in everything
    # revoking again changes nothing and records nothing more
    await client.delete(keys_url(workspace, made["id"]), cookies=cookies(testUser))
    assert len(await audit_events(workspace, API_KEY_REVOKED)) == 1


async def test_creating_with_a_list_records_the_key_and_each_form(
    client: AsyncClient, workspace, forms, roles_on
):
    made = (
        await create(
            client, workspace, role="VIEWER", formScope="listed", formIds=ids(forms)[:2]
        )
    ).json()
    created = await audit_events(workspace, API_KEY_CREATED)
    assert [(e.key_id, e.key_role, e.form_scope, e.count) for e in created] == [
        (made["id"], "VIEWER", "listed", 2)
    ]
    added = await audit_events(workspace, API_KEY_FORM_ADDED)
    assert sorted(e.form_id for e in added) == sorted(ids(forms)[:2])
    assert {e.key_id for e in added} == {made["id"]}


async def test_a_key_is_not_made_when_the_audit_cannot_be_written(
    client: AsyncClient, workspace, forms, roles_on, monkeypatch
):
    fail_audit(monkeypatch)
    for body in ({}, {"role": "VIEWER", "formScope": "listed", "formIds": ids(forms)[:1]}):
        refused = await create(client, workspace, **body)
        assert refused.status_code == 503, refused.text
        assert code(refused) == "audit_unavailable"
    assert await container.workspace_api_key_repo().list_by_workspace(workspace.id) == []


async def test_a_key_is_not_revoked_when_the_audit_cannot_be_written(
    client: AsyncClient, workspace, forms, roles_on, monkeypatch
):
    made = (
        await create(client, workspace, formScope="listed", formIds=ids(forms)[:1])
    ).json()
    fail_audit(monkeypatch)
    refused = await client.delete(keys_url(workspace, made["id"]), cookies=cookies(testUser))
    assert refused.status_code == 503
    assert (await stored(made["id"])).revoked is False
    assert await rows_of(workspace, made["id"]) == ids(forms)[:1]


# =========================================================================== revoke
async def test_revoking_deletes_the_keys_rows_and_nothing_else(
    client: AsyncClient, workspace, forms, roles_on
):
    one = (await create(client, workspace, formScope="listed", formIds=ids(forms))).json()
    two = (await create(client, workspace, formScope="listed", formIds=ids(forms)[:1])).json()
    assert len(await rows_of(workspace, one["id"])) == 3
    revoked = await client.delete(keys_url(workspace, one["id"]), cookies=cookies(testUser))
    assert revoked.status_code == 200
    assert await rows_of(workspace, one["id"]) == []
    assert await rows_of(workspace, two["id"]) == ids(forms)[:1]
    row = await stored(one["id"])
    # the key stays (revoked) with what it was, so the audit and "last used" remain
    assert row.revoked is True and row.form_scope == "listed"
    # and in the list a revoked key shows no forms
    listed = {
        k["id"]: k
        for k in (await client.get(keys_url(workspace), cookies=cookies(testUser))).json()
    }
    assert listed[one["id"]]["revoked"] is True and listed[one["id"]]["forms"] == []


async def test_a_key_of_another_workspace_is_not_found(
    client: AsyncClient, workspace, forms, roles_on
):
    other = await _other_workspace()
    foreign = await make_key(other, testUser1)
    for call in (
        client.delete(keys_url(workspace, foreign.id), cookies=cookies(testUser)),
        client.patch(
            keys_url(workspace, foreign.id), json={"role": "VIEWER"}, cookies=cookies(testUser)
        ),
    ):
        assert (await call).status_code == 404
    assert (await stored(foreign.id)).revoked is False and (await stored(foreign.id)).role is None


# =========================================================================== edit
async def test_an_edit_changes_the_role_and_audits_it(
    client: AsyncClient, workspace, roles_on
):
    made = (await create(client, workspace, role="EDITOR", scopes=READ)).json()
    narrowed = await patch(client, workspace, made["id"], role="VIEWER")
    assert narrowed.status_code == 200, narrowed.text
    assert narrowed.json()["role"] == "VIEWER" and "token" not in narrowed.json()
    widened = await patch(client, workspace, made["id"], role=None)
    assert widened.status_code == 200 and widened.json()["role"] is None
    events = await audit_events(workspace, API_KEY_ROLE_CHANGED)
    assert [(e.key_role_before, e.key_role, e.widened) for e in events] == [
        ("EDITOR", "VIEWER", False),
        ("VIEWER", "creator", True),
    ]
    # nothing changed that was not asked for
    row = await stored(made["id"])
    assert (row.role, row.scopes, row.name, str(row.created_by)) == (
        None, READ, NAME, str(testUser.id),
    )
    # the same role again is no change and no entry
    await patch(client, workspace, made["id"], role=None)
    assert len(await audit_events(workspace, API_KEY_ROLE_CHANGED)) == 2


async def test_an_edit_may_rename_without_touching_the_rest(
    client: AsyncClient, workspace, forms, roles_on
):
    made = (
        await create(client, workspace, role="VIEWER", formScope="listed", formIds=ids(forms)[:1])
    ).json()
    renamed = await patch(client, workspace, made["id"], name="  renamed  ")
    assert renamed.status_code == 200 and renamed.json()["name"] == "renamed"
    assert (renamed.json()["role"], renamed.json()["formScope"]) == ("VIEWER", "listed")
    assert await rows_of(workspace, made["id"]) == ids(forms)[:1]
    assert await audit_events(workspace, API_KEY_ROLE_CHANGED, API_KEY_SCOPE_CHANGED) == []


async def test_widening_the_list_is_allowed_and_audited_as_widened(
    client: AsyncClient, workspace, forms, roles_on
):
    made = (
        await create(client, workspace, role="VIEWER", formScope="listed", formIds=ids(forms)[:1])
    ).json()
    widened = await patch(client, workspace, made["id"], formIds=ids(forms)[:3])
    assert widened.status_code == 200, widened.text
    assert {f["id"] for f in widened.json()["forms"]} == set(ids(forms))
    assert await rows_of(workspace, made["id"]) == sorted(ids(forms))
    scope = (await audit_events(workspace, API_KEY_SCOPE_CHANGED))[-1]
    assert (scope.key_id, scope.form_scope, scope.count, scope.widened) == (
        made["id"], "listed", 3, True,
    )
    added = await audit_events(workspace, API_KEY_FORM_ADDED)
    assert sorted(e.form_id for e in added[1:]) == sorted(ids(forms)[1:])


async def test_narrowing_the_list_is_not_widening(
    client: AsyncClient, workspace, forms, roles_on
):
    made = (
        await create(client, workspace, formScope="listed", formIds=ids(forms))
    ).json()
    narrowed = await patch(client, workspace, made["id"], formIds=ids(forms)[:1])
    assert narrowed.status_code == 200, narrowed.text
    assert await rows_of(workspace, made["id"]) == ids(forms)[:1]
    scope = (await audit_events(workspace, API_KEY_SCOPE_CHANGED))[-1]
    assert (scope.count, scope.widened) == (1, False)
    removed = await audit_events(workspace, API_KEY_FORM_REMOVED)
    assert sorted(e.form_id for e in removed) == sorted(ids(forms)[1:])
    # to nothing at all: the key opens no form, it does not become unlimited
    empty = await patch(client, workspace, made["id"], formIds=[])
    assert empty.status_code == 200 and empty.json()["forms"] == []
    row = await stored(made["id"])
    assert row.form_scope == "listed" and await rows_of(workspace, made["id"]) == []


async def test_going_from_all_forms_to_a_list_and_back(
    client: AsyncClient, workspace, forms, roles_on
):
    made = (await create(client, workspace)).json()
    # a list needs its forms
    refused = await patch(client, workspace, made["id"], formScope="listed")
    assert refused.status_code == 400 and code(refused) == "form_ids_required"
    refused = await patch(client, workspace, made["id"], formIds=ids(forms)[:1])
    assert refused.status_code == 400 and code(refused) == "form_ids_need_listed_scope"
    limited = await patch(
        client, workspace, made["id"], formScope="listed", formIds=ids(forms)[:2]
    )
    assert limited.status_code == 200, limited.text
    assert await rows_of(workspace, made["id"]) == sorted(ids(forms)[:2])
    assert (await audit_events(workspace, API_KEY_SCOPE_CHANGED))[-1].widened is False
    # back to every form: the rows go, and it is a widening
    open_again = await patch(client, workspace, made["id"], formScope="all")
    assert open_again.status_code == 200 and open_again.json()["forms"] == []
    assert await rows_of(workspace, made["id"]) == []
    scope = (await audit_events(workspace, API_KEY_SCOPE_CHANGED))[-1]
    assert (scope.form_scope, scope.widened) == ("all", True)
    assert len(await audit_events(workspace, API_KEY_FORM_REMOVED)) == 2


async def test_a_role_change_rewrites_the_rows_to_the_new_role(
    client: AsyncClient, workspace, forms, roles_on
):
    made = (
        await create(client, workspace, role="EDITOR", formScope="listed", formIds=ids(forms)[:1])
    ).json()
    await patch(client, workspace, made["id"], role="VIEWER")
    rows = await container.form_access_grant_repo().for_key(workspace.id, made["id"])
    assert [r.role for r in rows] == ["VIEWER"]


async def test_an_edit_runs_the_same_matrix_as_a_create(
    client: AsyncClient, workspace, forms, roles_on
):
    made = (
        await create(client, workspace, scopes=["forms:read", "forms:write"])
    ).json()
    refused = await patch(client, workspace, made["id"], role="REVIEWER")
    assert refused.status_code == 400 and code(refused) == "scope_not_allowed_by_role"
    assert "forms:write" in refused.json()["message"]
    assert (await stored(made["id"])).role is None
    # a key that can delete forms cannot be limited to a list
    deleter = (await create(client, workspace, scopes=["forms:delete"])).json()
    refused = await patch(
        client, workspace, deleter["id"], formScope="listed", formIds=ids(forms)[:1]
    )
    assert refused.status_code == 400 and code(refused) == "scope_not_allowed_for_listed_key"
    assert (await stored(deleter["id"])).form_scope == "all"
    assert await rows_of(workspace, deleter["id"]) == []


async def test_a_list_that_drops_a_submission_form_is_refused(
    client: AsyncClient, workspace, forms, roles_on, monkeypatch
):
    monkeypatch.setattr(settings, "SUBMISSIONS_API_ENABLED", True)
    made = (
        await create(
            client,
            workspace,
            scopes=["submissions:write"],
            formScope="listed",
            formIds=ids(forms)[:2],
            submissionFormIds=ids(forms)[1:2],
        )
    ).json()
    refused = await patch(client, workspace, made["id"], formIds=ids(forms)[:1])
    assert refused.status_code == 400 and code(refused) == "submission_form_outside_list"
    assert await rows_of(workspace, made["id"]) == sorted(ids(forms)[:2])
    # and a list that makes the key a listed key must keep the submission forms
    other = (
        await create(
            client, workspace, scopes=["submissions:write"], submissionFormIds=ids(forms)[:1]
        )
    ).json()
    refused = await patch(
        client, workspace, other["id"], formScope="listed", formIds=ids(forms)[1:2]
    )
    assert refused.status_code == 400 and code(refused) == "submission_form_outside_list"


async def test_what_a_key_does_and_who_made_it_cannot_be_edited(
    client: AsyncClient, workspace, roles_on
):
    made = (await create(client, workspace)).json()
    for body in (
        {"scopes": ["forms:write"]},
        {"createdBy": str(RecordId())},
        {"revoked": False},
        {"keyHash": "x"},
        {"prefix": "bc_00000000"},
        {"submissionFormIds": []},
        {"role": "VIEWER", "token": "bc_x"},
    ):
        refused = await patch(client, workspace, made["id"], **body)
        assert refused.status_code == 422, (body, refused.text)
    row = await stored(made["id"])
    assert (row.role, row.scopes, str(row.created_by), row.revoked) == (
        None, READ, str(testUser.id), False,
    )


async def test_a_revoked_key_cannot_be_edited(
    client: AsyncClient, workspace, roles_on
):
    made = (await create(client, workspace)).json()
    await client.delete(keys_url(workspace, made["id"]), cookies=cookies(testUser))
    refused = await patch(client, workspace, made["id"], role="VIEWER")
    assert refused.status_code == 409 and code(refused) == "key_revoked"
    assert (await stored(made["id"])).role is None


async def test_a_key_cannot_be_given_a_role_above_the_person_it_acts_as(
    client: AsyncClient, workspace, roles_on
):
    """The key follows its creator at every request; the role may not even be
    set above them: an Admin's key made by someone since demoted to Reviewer."""
    from tests.app.form_access.test_key_roles import set_roles

    creator = await admin_creator(workspace)
    key = await make_key(workspace, creator, scopes=READ)
    await set_roles(workspace, creator, "REVIEWER")
    refused = await patch(client, workspace, str(key.id), role="EDITOR")
    assert refused.status_code == 403 and code(refused) == "key_role_exceeds_creator"
    narrower = await patch(client, workspace, str(key.id), role="VIEWER")
    assert narrower.status_code == 200, narrower.text
    # as its creator is always possible: it follows them
    assert (await patch(client, workspace, str(key.id), role=None)).status_code == 200


async def test_an_edit_is_not_made_when_the_audit_cannot_be_written(
    client: AsyncClient, workspace, forms, roles_on, monkeypatch
):
    made = (
        await create(client, workspace, role="VIEWER", formScope="listed", formIds=ids(forms)[:1])
    ).json()
    fail_audit(monkeypatch)
    refused = await patch(
        client, workspace, made["id"], role=None, formScope="listed", formIds=ids(forms)
    )
    assert refused.status_code == 503 and code(refused) == "audit_unavailable"
    row = await stored(made["id"])
    assert (row.role, row.form_scope) == ("VIEWER", "listed")
    assert await rows_of(workspace, made["id"]) == ids(forms)[:1]


async def test_an_edit_never_writes_over_a_revocation_made_meanwhile(workspace, roles_on):
    """``update_limits`` locks and re-reads: a key revoked since the caller read
    it is not brought back, and changes nothing."""
    admin = await admin_creator(workspace)
    key = await make_key(workspace, admin, scopes=READ)
    repo = container.workspace_api_key_repo()
    assert await repo.revoke_one(workspace.id, key.id) is True
    assert (
        await repo.update_limits(workspace.id, key.id, name="x", role="VIEWER", form_scope="all")
        is None
    )
    row = await stored(key.id)
    assert (row.revoked, row.role, row.name) == (True, None, "a key")
    # revoking is a no-op the second time, and another workspace's id changes nothing
    assert await repo.revoke_one(workspace.id, key.id) is False
    other = await make_key(workspace, admin, scopes=READ)
    assert await repo.revoke_one(RecordId(), other.id) is False
    assert (await stored(other.id)).revoked is False


# =========================================================================== lifecycle
async def test_every_revocation_path_deletes_the_keys_rows(
    client: AsyncClient, workspace, forms, roles_on
):
    """Member removal, directory deprovisioning, account deletion and the end of
    a workspace revoke keys; a key's rows must not outlive it."""
    lifecycle = container.api_key_lifecycle()
    repo = container.form_access_grant_repo()

    async def listed_key(creator):
        key = await make_key(
            workspace, creator, scopes=READ, form_scope="listed", forms=ids(forms)[:2]
        )
        assert len(await rows_of(workspace, key.id)) == 2
        return key

    class Actor:
        id = str(testUser.id)
        sid = None

    # directory deprovisioning
    person = await admin_creator(workspace)
    key = await listed_key(person)
    assert await lifecycle.revoke_member_keys(workspace.id, person.id, Actor, "scim_deprovisioned") == 1
    assert (await stored(key.id)).revoked is True and await rows_of(workspace, key.id) == []
    # account deletion
    person = await admin_creator(workspace)
    key = await listed_key(person)
    assert await lifecycle.revoke_account_keys(person.id) == 1
    assert await rows_of(workspace, key.id) == []
    # the end of the workspace: every key, whoever made it
    mine, theirs = await listed_key(await admin_creator(workspace)), await listed_key(testUser)
    assert await lifecycle.revoke_workspace_keys([workspace.id]) == 2
    for key in (mine, theirs):
        assert (await stored(key.id)).revoked is True
        assert await rows_of(workspace, key.id) == []
    assert await repo.count_for_subject(workspace.id, SUBJECT_KEY, mine.id) == 0


async def test_removing_a_member_deletes_the_rows_of_their_keys(
    client: AsyncClient, workspace, forms, roles_on, monkeypatch
):
    from unittest.mock import patch as mock_patch

    async def lookup(*args, **kwargs):
        users = [str(i) for i in (kwargs.get("params") or {}).get("user_ids", [])]
        return {"users_info": [{"_id": i, "email": f"{i}@example.com"} for i in users]}

    person = await admin_creator(workspace)
    bystander = await admin_creator(workspace)
    key = await make_key(workspace, person, scopes=READ, form_scope="listed", forms=ids(forms)[:2])
    kept = await make_key(workspace, bystander, scopes=READ, form_scope="listed", forms=ids(forms)[:1])
    with mock_patch("common.services.http_client.HttpClient.get", side_effect=lookup):
        removed = await client.delete(
            f"{api(workspace)}/members/{person.id}", cookies=cookies(testUser)
        )
    assert removed.status_code == 200, removed.text
    assert (await stored(key.id)).revoked is True
    assert await rows_of(workspace, key.id) == []
    assert await rows_of(workspace, kept.id) == ids(forms)[:1]


async def test_deleting_a_workspace_revokes_the_keys_of_its_other_members(
    client: AsyncClient, workspace, forms, roles_on
):
    """The owner's account and workspaces go; another member's key, which no
    one would ever use again, is revoked too instead of staying live for good."""
    member = await admin_creator(workspace)
    key = await make_key(workspace, member, scopes=READ, form_scope="listed", forms=ids(forms)[:1])
    await container.workspace_user_service().forget_access_of_workspaces([workspace.id])
    assert (await stored(key.id)).revoked is True
    assert await rows_of(workspace, key.id) == []
    assert REVOKED_WORKSPACE_DELETED == "workspace_deleted"


# =========================================================================== end to end
async def test_a_key_made_by_the_route_is_held_to_its_list(
    client: AsyncClient, workspace, roles_on
):
    from tests.app.form_access.test_key_roles import BASE, TOKENS, _spec_form

    # forms the public API can show (built from pages), made through it
    owner = await make_key(workspace, testUser)
    first = await _spec_form(client, owner, "First")
    second = await _spec_form(client, owner, "Second")
    made = (
        await create(
            client,
            workspace,
            role="VIEWER",
            scopes=["forms:read"],
            formScope="listed",
            formIds=[first],
        )
    ).json()
    auth = {"Authorization": f"Bearer {made['token']}"}
    TOKENS[made["id"]] = made["token"]
    inside = await client.get(f"{BASE}/forms/{first}", headers=auth)
    outside = await client.get(f"{BASE}/forms/{second}", headers=auth)
    ghost = await client.get(f"{BASE}/forms/{RecordId()}", headers=auth)
    assert inside.status_code == 200, inside.text
    assert outside.status_code == ghost.status_code == 404
    assert outside.json() == ghost.json()
    # widen it from the keys page: the very next request sees it
    await patch(client, workspace, made["id"], formIds=[first, second])
    assert (await client.get(f"{BASE}/forms/{second}", headers=auth)).status_code == 200
    # narrow it to nothing
    await patch(client, workspace, made["id"], formIds=[])
    assert (await client.get(f"{BASE}/forms/{first}", headers=auth)).status_code == 404
    # revoke: the key no longer authenticates
    await client.delete(keys_url(workspace, made["id"]), cookies=cookies(testUser))
    assert (await client.get(f"{BASE}/forms/{first}", headers=auth)).status_code == 401


async def test_the_titles_a_reader_may_not_see_are_left_out(
    client: AsyncClient, workspace, forms, roles_on, monkeypatch
):
    """The list names every form of a key; the title only where the reader may
    open the form."""
    made = (await create(client, workspace, formScope="listed", formIds=ids(forms)[:2])).json()
    service = container.api_key_service()

    async def only_first(user, workspace_id, form_ids, permission):
        return [f for f in form_ids if f == ids(forms)[0]]

    monkeypatch.setattr(service._authorization, "restrict_to_visible", only_first)
    listed = await service.list_keys(workspace.id, testUser)
    by_id = {f.id: f.title for f in listed[0].forms}
    assert set(by_id) == set(ids(forms)[:2])
    assert by_id[ids(forms)[0]] and by_id[ids(forms)[1]] is None
