"""Reading one form by id or slug (``GET /workspaces/{id}/forms/{form}``).

A draft (``published`` false, and the draft fallback ``published=true&draft=true``
for a form never published) is for members who may read the workspace's forms
(``form.read``), as in the forms list and search. Anyone else gets 403 before
any lookup, the same for a form that exists and one that does not. Published
forms stay readable by anyone, signed in or not, as before."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from common.ids import RecordId
from common.models.standard_form import StandardForm
from common.models.user import User
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.form_service import FormService
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser

DRAFT_TITLE = "draft-read secret draft"
PUBLISHED_TITLE = "draft-read published"

outsider = User(id=str(RecordId()), sub="draft-read-outsider@example.com")
disabled_admin = User(id=str(RecordId()), sub="draft-read-disabled@example.com")
viewer = User(id=str(RecordId()), sub="draft-read-viewer@example.com")
editor = User(id=str(RecordId()), sub="draft-read-editor@example.com")


@pytest.fixture(autouse=True)
def auth_users():
    """Staff reads name the importer: the auth service knows no one here."""
    mock = AsyncMock(return_value={"users_info": []})
    with patch.object(FormService, "fetch_user_details", mock):
        yield mock


def _cookies(user: User) -> dict:
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


async def _member(workspace, user, role, disabled=False):
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id,
            user_id=user.id,
            roles=[role],
            disabled=disabled,
        )
    )


async def _draft(workspace, title=DRAFT_TITLE):
    """A form of ``workspace`` that was never published."""
    return await container.workspace_form_service().create_form(
        workspace.id, StandardForm(title=title, fields=[]), testUser
    )


async def _slug(workspace, form_id) -> str:
    repo = container.workspace_form_repo()
    association = await repo.get_workspace_form_with_custom_slug_form_id(
        workspace_id=workspace.id, custom_url=form_id
    )
    return association.settings.custom_url


def _read(workspace, form_id, query=""):
    return f"/api/v1/workspaces/{workspace.id}/forms/{form_id}{query}"


async def _refusable(workspace, who) -> User:
    if who == "disabled member":
        await _member(workspace, disabled_admin, WorkspaceRoles.ADMIN, disabled=True)
        return disabled_admin
    return outsider


REFUSED = pytest.mark.parametrize(
    "who", ["outsider", "disabled member"], ids=["non-member", "disabled-member"]
)


@REFUSED
@pytest.mark.parametrize("by", ["id", "slug"])
async def test_a_draft_is_refused_without_form_read(
    client: AsyncClient, workspace, who, by
):
    form = await _draft(workspace)
    user = await _refusable(workspace, who)
    key = form.form_id if by == "id" else await _slug(workspace, form.form_id)

    read = await client.get(_read(workspace, key), cookies=_cookies(user))

    assert read.status_code == 403, read.text
    assert DRAFT_TITLE not in read.text


@REFUSED
async def test_the_refusal_does_not_tell_whether_the_form_exists(
    client: AsyncClient, workspace, who
):
    user = await _refusable(workspace, who)

    read = await client.get(
        _read(workspace, str(RecordId())), cookies=_cookies(user)
    )

    assert read.status_code == 403, read.text


async def test_a_signed_out_draft_read_still_needs_signing_in(
    client: AsyncClient, workspace
):
    form = await _draft(workspace)

    read = await client.get(_read(workspace, form.form_id))

    assert read.status_code == 401, read.text
    assert DRAFT_TITLE not in read.text


@pytest.mark.parametrize("role", ["owner", "editor", "viewer"])
async def test_members_with_form_read_get_the_draft(
    client: AsyncClient, workspace, role
):
    form = await _draft(workspace)
    user = testUser
    if role == "editor":
        user = editor
        await _member(workspace, editor, WorkspaceRoles.EDITOR)
    elif role == "viewer":
        user = viewer
        await _member(workspace, viewer, WorkspaceRoles.VIEWER)

    by_id = await client.get(_read(workspace, form.form_id), cookies=_cookies(user))
    by_slug = await client.get(
        _read(workspace, await _slug(workspace, form.form_id)),
        cookies=_cookies(user),
    )

    for read in (by_id, by_slug):
        assert read.status_code == 200, read.text
        assert read.json()["formId"] == form.form_id
        assert read.json()["title"] == DRAFT_TITLE


@pytest.mark.parametrize("signed_in", [True, False], ids=["non-member", "anonymous"])
async def test_the_draft_fallback_is_staff_only(
    client: AsyncClient, workspace, test_user_cookies, signed_in
):
    """``published=true&draft=true`` serves a never-published form's draft
    to staff (the form dashboard); anyone else gets what a published read
    gives them, which for a never-published form is nothing."""
    form = await _draft(workspace)
    path = _read(workspace, form.form_id, "?published=true&draft=true")

    staff = await client.get(path, cookies=test_user_cookies)
    other = await client.get(path, cookies=_cookies(outsider) if signed_in else None)

    assert staff.status_code == 200, staff.text
    assert staff.json()["title"] == DRAFT_TITLE
    assert other.status_code == 404, other.text
    assert DRAFT_TITLE not in other.text


async def test_a_non_member_reads_an_unknown_form_published_as_not_found(
    client: AsyncClient, workspace
):
    for query in ("?published=true", "?published=true&draft=true"):
        read = await client.get(
            _read(workspace, "no-such-form", query), cookies=_cookies(outsider)
        )

        assert read.status_code == 404, read.text


@pytest.mark.parametrize("signed_in", [True, False], ids=["non-member", "anonymous"])
async def test_a_published_form_stays_readable_by_anyone(
    client: AsyncClient, workspace, test_user_cookies, signed_in
):
    """Anyone reads the published version, never the draft edited since."""
    form = await _draft(workspace, title=PUBLISHED_TITLE)
    await container.workspace_form_service().publish_form(
        workspace.id, form.form_id, testUser
    )
    edited = await client.patch(
        _read(workspace, form.form_id),
        data={"form_body": json.dumps({"title": DRAFT_TITLE, "fields": []})},
        cookies=test_user_cookies,
    )
    assert edited.status_code == 200, edited.text
    cookies = _cookies(outsider) if signed_in else None

    for key in (form.form_id, await _slug(workspace, form.form_id)):
        for query in ("?published=true", "?published=true&draft=true"):
            read = await client.get(_read(workspace, key, query), cookies=cookies)
            assert read.status_code == 200, read.text
            assert read.json()["formId"] == form.form_id
            assert read.json()["title"] == PUBLISHED_TITLE
            assert not read.json().get("unauthorized")
            assert DRAFT_TITLE not in read.text
    if signed_in:
        draft = await client.get(_read(workspace, form.form_id), cookies=cookies)
        assert draft.status_code == 403, draft.text
        assert DRAFT_TITLE not in draft.text


async def _hide(client, workspace, form_id, cookies):
    hidden = await client.patch(
        _read(workspace, form_id, "/settings"),
        json={"hidden": True},
        cookies=cookies,
    )
    assert hidden.status_code == 200, hidden.text


async def test_a_hidden_form_reads_as_before(
    client: AsyncClient, workspace, test_user_cookies
):
    """A hidden form's draft is its creator's (other members get 404, as
    before); a published read by anyone else gets the placeholder without
    questions, as before."""
    form = await _draft(workspace, title=PUBLISHED_TITLE)
    await container.workspace_form_service().publish_form(
        workspace.id, form.form_id, testUser
    )
    await _hide(client, workspace, form.form_id, test_user_cookies)
    await _member(workspace, viewer, WorkspaceRoles.VIEWER)

    own = await client.get(_read(workspace, form.form_id), cookies=test_user_cookies)
    member = await client.get(_read(workspace, form.form_id), cookies=_cookies(viewer))
    outsiders_draft = await client.get(
        _read(workspace, form.form_id), cookies=_cookies(outsider)
    )
    published = {
        "non-member": await client.get(
            _read(workspace, form.form_id, "?published=true"),
            cookies=_cookies(outsider),
        ),
        "anonymous": await client.get(
            _read(workspace, form.form_id, "?published=true")
        ),
    }

    assert own.status_code == 200, own.text
    assert own.json()["title"] == PUBLISHED_TITLE
    assert member.status_code == 404, member.text
    assert outsiders_draft.status_code == 403, outsiders_draft.text
    for who, read in published.items():
        assert read.status_code == 200, f"{who}: {read.text}"
        assert read.json()["formId"] == form.form_id
        assert not read.json().get("fields"), who
