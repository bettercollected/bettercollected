"""Copying a form needs a permission on each side, decided for the same person:
``form.read`` on the source form, ``form.create`` in the target workspace (or
``form.edit`` on the target form), and for a restricted source an Owner, an Admin
or its creator. A workspace the caller is not in answers as one that does not exist."""

import pytest
from common.constants import MESSAGE_FORBIDDEN as FORBIDDEN
from common.ids import RecordId
from common.models.user import User

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.form_access_grant import ROLE_EDITOR
from backend.app.schemas.workspace_audit_event import FORM_COPIED_OUT, FORM_PROMOTED
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.form_access.model import MODE_RESTRICTED
from backend.config import settings
from tests.app.controllers.data import testUser, testUser1
from tests.app.form_access.helpers import add_member, audit_events, cookies, grant
from tests.app.form_promotion.helpers import (
    body,
    create_source,
    headers,
    make_member,
    on,
    spec_document,
    url,
)

pytestmark = pytest.mark.asyncio

R = WorkspaceRoles


@pytest.fixture(autouse=True)
def switched_on(monkeypatch):
    on(monkeypatch)


@pytest.fixture()
async def world(workspace, workspace_1):
    form_id, etag = await create_source(workspace)
    return type(
        "World",
        (),
        {"a": workspace, "b": workspace_1, "form_id": form_id, "etag": etag},
    )


async def member(workspace, *roles) -> User:
    return await add_member(workspace, *[r.value for r in roles])


async def both(w, source: R, target: R) -> User:
    user = await member(w.a, source)
    await make_member(w.b, user, target.value)
    return user


async def preview(client, w, user, **more):
    return await client.post(
        url(w.a, w.form_id, "/promotion/preview"),
        json=body(w.b, **more),
        cookies=cookies(user),
    )


async def apply(client, w, user, **more):
    return await client.post(
        url(w.a, w.form_id, "/promotion/apply"),
        json=body(w.b, sourceEtag=w.etag, **more),
        cookies=cookies(user),
        headers=headers(),
    )


# -- the target side, for a new form -----------------------------------------------------------
@pytest.mark.parametrize(
    "target_role, allowed",
    [
        (R.OWNER, True),
        (R.ADMIN, True),
        (R.EDITOR, True),
        (R.REVIEWER, False),
        (R.VIEWER, False),
        (R.PRIVACY_OFFICER, False),
    ],
)
async def test_a_new_form_needs_form_create_in_the_target(
    client, world, target_role, allowed
):
    user = await both(world, R.EDITOR, target_role)
    seen = await preview(client, world, user)
    done = await apply(client, world, user)
    if allowed:
        assert (seen.status_code, done.status_code) == (200, 201), done.text
        # the person who copied it is its creator in the target
        link = await container.workspace_form_repo().find_workspace_form(
            world.b.id, done.json()["formId"]
        )
        assert str(link.user_id) == user.id
    else:
        assert (seen.status_code, done.status_code) == (403, 403)
        assert seen.json() == done.json() == FORBIDDEN
        assert await audit_events(world.b, FORM_PROMOTED) == []


# -- the source side ------------------------------------------------------------------------
@pytest.mark.parametrize(
    "source_role, allowed",
    [
        (R.VIEWER, True),  # may read it: nothing is added beyond what they hold
        (R.REVIEWER, True),
        (R.PRIVACY_OFFICER, True),
        (R.EDITOR, True),
    ],
)
async def test_the_source_needs_form_read_only(client, world, source_role, allowed):
    user = await both(world, source_role, R.ADMIN)
    assert (await preview(client, world, user)).status_code == 200
    assert (await apply(client, world, user)).status_code == 201


async def test_someone_who_is_not_in_the_source_workspace_is_refused(client, world):
    outsider = await member(world.b, R.OWNER)
    seen = await preview(client, world, outsider)
    done = await apply(client, world, outsider)
    assert seen.status_code == done.status_code == 403
    assert await audit_events(world.a, FORM_COPIED_OUT) == []


async def test_a_form_of_another_workspace_is_no_form_here(
    client, world, workspace_1
):
    """B's form under A's path: the same 404 as a form that does not exist."""
    own_form, _ = await create_source(workspace_1, user=testUser1)
    user = await both(world, R.ADMIN, R.ADMIN)
    stolen = await client.post(
        url(world.a, own_form, "/promotion/preview"),
        json=body(world.b),
        cookies=cookies(user),
    )
    ghost = await client.post(
        url(world.a, str(RecordId()), "/promotion/preview"),
        json=body(world.b),
        cookies=cookies(user),
    )
    assert stolen.status_code == ghost.status_code == 404
    assert stolen.json() == ghost.json()


# -- a target workspace the caller is not in ------------------------------------------------------
async def test_a_target_workspace_the_caller_is_not_in_does_not_exist(
    client, world, workspace_pro
):
    user = await member(world.a, R.ADMIN)
    # not a member of B at all
    real = await preview(client, world, user)
    unknown = await client.post(
        url(world.a, world.form_id, "/promotion/preview"),
        json={"targetWorkspaceId": str(RecordId())},
        cookies=cookies(user),
    )
    assert real.status_code == unknown.status_code == 404
    assert real.json() == unknown.json()
    done = await apply(client, world, user)
    assert done.status_code == 404 and done.json() == unknown.json()
    assert await audit_events(world.a, FORM_COPIED_OUT) == []


async def test_a_disabled_membership_in_the_target_counts_as_none(client, world):
    user = await member(world.a, R.ADMIN)
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=world.b.id,
            user_id=user.id,
            roles=[R.ADMIN.value],
            disabled=True,
        )
    )
    assert (await preview(client, world, user)).status_code == 404


# -- the target side, for an existing form ---------------------------------------------------------
async def _target_form(world, creator=testUser1):
    form_id, _, _ = await container.form_spec_writer().create(
        world.b.id, spec_document(title="Doel"), creator
    )
    spec, etag = await container.form_spec_writer().read(world.b.id, form_id)
    return form_id, etag


@pytest.mark.parametrize(
    "target_role, status",
    [(R.EDITOR, 200), (R.ADMIN, 200), (R.VIEWER, 403), (R.REVIEWER, 403)],
)
async def test_an_existing_target_needs_form_edit_on_it(
    client, world, target_role, status
):
    user = await both(world, R.EDITOR, target_role)
    form_id, etag = await _target_form(world)
    seen = await preview(client, world, user, targetFormId=form_id)
    done = await apply(client, world, user, targetFormId=form_id, targetEtag=etag)
    assert seen.status_code == status
    assert done.status_code == status, done.text


async def test_a_target_form_of_another_workspace_is_no_form_of_the_target(
    client, world, workspace
):
    """A's own form named as the target in B: 404, as for an unknown id."""
    user = await both(world, R.ADMIN, R.ADMIN)
    other, _ = await create_source(world.a)
    named = await preview(client, world, user, targetFormId=other)
    ghost = await preview(client, world, user, targetFormId=str(RecordId()))
    assert named.status_code == ghost.status_code == 404
    assert named.json() == ghost.json()


async def test_a_target_form_closed_to_the_caller_is_a_404(
    client, world, monkeypatch
):
    user = await both(world, R.EDITOR, R.EDITOR)
    form_id, etag = await _target_form(world)
    await container.workspace_form_repo().set_access_mode(
        world.b.id, form_id, MODE_RESTRICTED
    )
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    closed = await preview(client, world, user, targetFormId=form_id)
    ghost = await preview(client, world, user, targetFormId=str(RecordId()))
    assert closed.status_code == ghost.status_code == 404
    assert closed.json() == ghost.json()
    # the picker does not list it either
    listed = await client.get(
        url(world.a, world.form_id, "/promotion/targets"),
        params={"targetWorkspaceId": str(world.b.id)},
        cookies=cookies(user),
    )
    assert listed.json()["items"] == []


async def test_the_picker_lists_nothing_to_a_member_who_may_edit_nothing_there(
    client, world
):
    viewer = await both(world, R.EDITOR, R.VIEWER)
    await _target_form(world)
    listed = await client.get(
        url(world.a, world.form_id, "/promotion/targets"),
        params={"targetWorkspaceId": str(world.b.id)},
        cookies=cookies(viewer),
    )
    assert listed.status_code == 200
    assert listed.json() == {"items": [], "more": False}


# -- the restricted source --------------------------------------------------------------------------
@pytest.fixture()
async def restricted(world, monkeypatch):
    """A restricted form made by an Editor (its creator), with a grantee Editor,
    an Editor with no way in and an Admin. Everyone is an Admin of B."""
    creator = await member(world.a, R.EDITOR)
    form_id, etag = await create_source(world.a, user=creator)
    world.form_id, world.etag = form_id, etag
    await container.workspace_form_repo().set_access_mode(
        world.a.id, form_id, MODE_RESTRICTED
    )
    grantee = await member(world.a, R.EDITOR)
    await grant(world.a, form_id, grantee.id, ROLE_EDITOR)
    outsider = await member(world.a, R.EDITOR)
    admin = await member(world.a, R.ADMIN)
    for user in (creator, grantee, outsider, admin):
        await make_member(world.b, user, R.ADMIN.value)
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    world.people = dict(
        creator=creator, grantee=grantee, outsider=outsider, admin=admin
    )
    return world


async def test_only_an_owner_an_admin_or_the_creator_copy_a_restricted_form(
    client, restricted
):
    w, people = restricted, restricted.people
    for name in ("creator", "admin"):
        assert (await preview(client, w, people[name])).status_code == 200, name
        assert (await apply(client, w, people[name])).status_code == 201, name
    # a grantee may read and edit it, but the copy has a life of its own
    for call in (preview, apply):
        refused = await call(client, w, people["grantee"])
        assert refused.status_code == 403
        assert refused.json()["code"] == "promotion_from_restricted_form"
    # no way in: the 404 of a form that is not there
    for call in (preview, apply):
        assert (await call(client, w, people["outsider"])).status_code == 404
    assert len(await audit_events(w.b, FORM_PROMOTED)) == 2


async def test_the_form_file_of_a_restricted_form_follows_the_same_rule(
    client, restricted
):
    w, people = restricted, restricted.people
    path = url(w.a, w.form_id, "/spec-file")
    assert (await client.get(path, cookies=cookies(people["creator"]))).status_code == 200
    refused = await client.get(path, cookies=cookies(people["grantee"]))
    assert refused.status_code == 403
    assert refused.json()["code"] == "promotion_from_restricted_form"
    assert (await client.get(path, cookies=cookies(people["outsider"]))).status_code == 404


# -- an API key is not a person ----------------------------------------------------------------------
async def test_an_api_key_cannot_use_these_routes(world):
    """The acting user of a key has neither side's key semantics: a listed key
    cannot create, a key works in its own workspace only. Keys copy with the
    command line, one key for each workspace."""
    key_user = User(
        id=testUser.id,
        sub="api-key:ci",
        roles=["FORM_CREATOR"],
        auth_method="api_key",
    )
    service = container.form_promotion_service()
    from backend.app.models.dtos.form_promotion_dto import PromotionRequest

    request = PromotionRequest(target_workspace_id=world.b.id)
    with pytest.raises(HTTPException) as refusal:
        await service.preview(key_user, world.a.id, world.form_id, request)
    assert refusal.value.status_code == 403
    assert refusal.value.content["code"] == "promotion_needs_session"
    with pytest.raises(HTTPException):
        await service.spec_file(key_user, world.a.id, world.form_id)
    assert await audit_events(world.a, FORM_COPIED_OUT) == []


# -- a form that cannot be copied ----------------------------------------------------------------------
async def test_an_import_waiting_for_its_review_is_not_promotable(client, world):
    await container.workspace_form_repo().set_review_mark(
        world.a.id, world.form_id, True, "open_formulieren", "import-1"
    )
    user = await both(world, R.ADMIN, R.ADMIN)
    response = await preview(client, world, user)
    assert response.status_code == 422
    assert response.json()["code"] == "form_not_promotable"
