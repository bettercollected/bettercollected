"""A restricted form's structure goes only into a form that is restricted too.

A new form takes its source's mode in the same write as its link. An existing
target keeps its own mode (copying into a form never changes who may open it), so
a restricted source onto an existing OPEN target is refused: the preview says so
(``valid: false``, ``copyIsRestricted: false``), apply answers 409
``target_not_restricted``, and nothing is written or recorded.

Also: the counts of what does not move and where a form came from are for those
who may edit the form, and preview and the picker are rate limited."""

import datetime as dt

import pytest
from common.ids import RecordId

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.models.workspace import PromotedFrom
from backend.app.schemas.workspace_audit_event import FORM_COPIED_OUT, FORM_PROMOTED
from backend.app.services.form_access.model import MODE_RESTRICTED
from backend.config import settings
from tests.app.controllers.data import testUser
from tests.app.form_access.helpers import add_member, audit_events, cookies
from tests.app.form_promotion.helpers import (
    add_automations,
    body,
    create_source,
    headers,
    make_member,
    on,
    spec_document,
    stored_spec,
    url,
)
from tests.app.form_promotion.test_promotion_api import (  # noqa: F401
    _existing_target,
    apply,
    preview,
    world,
)

pytestmark = pytest.mark.asyncio

MESSAGE = "Restrict the target form first"


@pytest.fixture(autouse=True)
def switched_on(monkeypatch):
    on(monkeypatch)


async def restrict_source(world, monkeypatch):
    await container.workspace_form_repo().set_access_mode(
        world.a.id, world.form_id, MODE_RESTRICTED
    )
    monkeypatch.setattr(settings.form_access, "ENABLED", True)


async def refused_onto_open_target(client, world, target_workspace, target, etag):
    payload = body(target_workspace, targetFormId=target, targetEtag=etag)
    seen = await client.post(
        url(world.a, world.form_id, "/promotion/preview"),
        json=payload,
        cookies=cookies(testUser),
    )
    assert seen.status_code == 200, seen.text
    data = seen.json()
    # what will happen to the TARGET: it stays open
    assert data["valid"] is False and data["copyIsRestricted"] is False
    assert any(
        e.get("code") == "target_not_restricted" and e["message"] == MESSAGE
        for e in data["errors"]
    )
    done = await client.post(
        url(world.a, world.form_id, "/promotion/apply"),
        json={**payload, "sourceEtag": world.etag},
        cookies=cookies(testUser),
        headers=headers(),
    )
    assert done.status_code == 409, done.text
    assert done.json() == {"code": "target_not_restricted", "message": MESSAGE}
    # nothing written, nothing recorded, and the target was not restricted
    assert (await stored_spec(target_workspace, target))[0]["title"] == "Oud"
    assert await audit_events(world.a, FORM_COPIED_OUT) == []
    assert await audit_events(target_workspace, FORM_PROMOTED) == []
    link = await container.workspace_form_repo().find_workspace_form(
        target_workspace.id, target
    )
    assert link.settings.access_mode is None


async def test_onto_an_open_target_in_another_workspace(client, world, monkeypatch):
    await restrict_source(world, monkeypatch)
    target, etag = await _existing_target(world)
    await refused_onto_open_target(client, world, world.b, target, etag)


async def test_onto_an_open_target_in_the_same_workspace(client, world, monkeypatch):
    await restrict_source(world, monkeypatch)
    other, _, _ = await container.form_spec_writer().create(
        world.a.id, spec_document(**{"title": "Oud"}), testUser
    )
    _, etag = await stored_spec(world.a, other)
    await refused_onto_open_target(client, world, world.a, other, etag)


async def test_onto_a_restricted_target_it_is_allowed(client, world, monkeypatch):
    await restrict_source(world, monkeypatch)
    target, etag = await _existing_target(world)
    await container.workspace_form_repo().set_access_mode(
        world.b.id, target, MODE_RESTRICTED
    )
    seen = await preview(client, world, targetFormId=target)
    assert seen.json()["valid"] is True and seen.json()["copyIsRestricted"] is True
    done = await apply(client, world, targetFormId=target, targetEtag=etag)
    assert done.status_code == 200, done.text
    link = await container.workspace_form_repo().find_workspace_form(world.b.id, target)
    assert link.settings.access_mode == MODE_RESTRICTED


async def test_onto_a_new_form_it_still_comes_out_restricted(client, world, monkeypatch):
    await restrict_source(world, monkeypatch)
    seen = await preview(client, world)
    assert seen.json()["valid"] is True and seen.json()["copyIsRestricted"] is True
    done = await apply(client, world)
    assert done.status_code == 201, done.text
    link = await container.workspace_form_repo().find_workspace_form(
        world.b.id, done.json()["formId"]
    )
    assert link.settings.access_mode == MODE_RESTRICTED


async def test_an_open_source_onto_an_open_target_is_unchanged(client, world):
    target, etag = await _existing_target(world)
    seen = await preview(client, world, targetFormId=target)
    assert seen.json()["valid"] is True and seen.json()["copyIsRestricted"] is False
    assert (
        await apply(client, world, targetFormId=target, targetEtag=etag)
    ).status_code == 200


# -- the counts and the ids are for editors --------------------------------------------------------
async def test_a_reader_of_the_source_gets_no_counts(client, world):
    await add_automations(world.a, world.form_id, webhooks=2)
    viewer = await add_member(world.a, WorkspaceRoles.VIEWER.value)
    await make_member(world.b, viewer, WorkspaceRoles.ADMIN.value)
    seen = await preview(client, world, user=viewer)
    assert seen.status_code == 200, seen.text
    assert seen.json()["notCarried"] is None
    done = await apply(client, world, user=viewer)
    assert done.status_code == 201, done.text
    assert done.json()["notCarried"] is None
    # an editor still gets them
    assert (await preview(client, world)).json()["notCarried"]["webhooks"] == 2


async def test_a_reader_of_the_target_does_not_see_where_a_form_came_from(
    client, workspace, mock_aiohttp_get_request
):
    form_id, _ = await create_source(workspace)
    await container.workspace_form_service().publish_form(
        workspace.id, form_id, testUser
    )
    await container.workspace_form_repo().set_promoted_from(
        workspace.id,
        form_id,
        PromotedFrom(
            workspace_id="a1" * 12,
            form_id="b2" * 12,
            at=dt.datetime(2026, 11, 2, tzinfo=dt.timezone.utc),
            by="c3" * 12,
            source_hash="h",
            not_carried={"webhooks": 3},
        ),
    )
    viewer = await add_member(workspace, WorkspaceRoles.VIEWER.value)
    editor = await add_member(workspace, WorkspaceRoles.COLLABORATOR.value)
    base = f"/api/v1/workspaces/{workspace.id}/forms"
    with mock_aiohttp_get_request:
        for user, sees in ((viewer, False), (editor, True), (testUser, True)):
            one = await client.get(f"{base}/{form_id}", cookies=cookies(user))
            assert one.status_code == 200, one.text
            listed = await client.get(base, cookies=cookies(user))
            assert listed.status_code == 200, listed.text
            for settings_ in (
                one.json()["settings"],
                listed.json()["items"][0]["settings"],
            ):
                assert (settings_["promotedFrom"] is not None) is sees, user.id
        found = await client.post(
            f"{base}/search",
            params={"query": "Aanmelding"},
            cookies=cookies(viewer),
        )
        assert found.status_code == 200, found.text
        assert "b2b2b2" not in found.text


# -- rate limits -------------------------------------------------------------------------------------
async def test_preview_and_the_picker_are_rate_limited_apart_from_apply(
    client, world, monkeypatch
):
    monkeypatch.setattr(settings.api_settings, "EDITOR_OPS_PER_WINDOW", 2)
    path = url(world.a, world.form_id, "/promotion/preview")
    statuses = [
        (
            await client.post(path, json=body(world.b), cookies=cookies(testUser))
        ).status_code
        for _ in range(3)
    ]
    assert statuses == [200, 200, 429]
    picker = await client.get(
        url(world.a, world.form_id, "/promotion/targets"),
        params={"targetWorkspaceId": str(world.b.id)},
        cookies=cookies(testUser),
    )
    assert picker.status_code == 429
    # a copy is counted on its own
    assert (await apply(client, world)).status_code == 201


async def test_a_target_opened_after_the_plan_is_refused_at_the_write(
    client, world, monkeypatch
):
    """The target's mode is read again right before the write: a target that was
    restricted when the copy was planned and opened since (no version tag changes
    with the mode) gets nothing."""
    from backend.app.services.form_access.model import MODE_WORKSPACE
    from backend.app.services.form_spec import writes

    await restrict_source(world, monkeypatch)
    target, etag = await _existing_target(world)
    repo = container.workspace_form_repo()
    await repo.set_access_mode(world.b.id, target, MODE_RESTRICTED)
    checked = writes._checked_spec

    async def opened_meanwhile(raw):
        result = await checked(raw)
        await repo.set_access_mode(world.b.id, target, MODE_WORKSPACE)
        return result

    monkeypatch.setattr(writes, "_checked_spec", opened_meanwhile)
    done = await apply(client, world, targetFormId=target, targetEtag=etag)
    assert done.status_code == 409, done.text
    assert done.json() == {"code": "target_not_restricted", "message": MESSAGE}
    assert (await stored_spec(world.b, target))[0]["title"] == "Oud"


async def test_a_target_opened_inside_the_write_is_refused_by_the_locked_check(
    client, world, monkeypatch
):
    """The mode is checked in the transaction of the write itself (under a share
    lock on the link), not before it: even a target opened after every earlier
    read of the write, right before its UPDATE, gets nothing."""
    from backend.app.repositories.postgres.forms import PostgresFormRepository
    from backend.app.services.form_access.model import MODE_WORKSPACE

    await restrict_source(world, monkeypatch)
    target, etag = await _existing_target(world)
    repo = container.workspace_form_repo()
    await repo.set_access_mode(world.b.id, target, MODE_RESTRICTED)
    stored_draft = PostgresFormRepository._stored_draft
    opened = []

    async def opened_after_the_last_read(self, form_id):
        found = await stored_draft(self, form_id)
        if str(form_id) == target and not opened:
            opened.append(True)
            await repo.set_access_mode(world.b.id, target, MODE_WORKSPACE)
        return found

    monkeypatch.setattr(PostgresFormRepository, "_stored_draft", opened_after_the_last_read)
    done = await apply(client, world, targetFormId=target, targetEtag=etag)
    assert opened == [True]
    assert done.status_code == 409, done.text
    assert done.json() == {"code": "target_not_restricted", "message": MESSAGE}
    assert (await stored_spec(world.b, target))[0]["title"] == "Oud"
