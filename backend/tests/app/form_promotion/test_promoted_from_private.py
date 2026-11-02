"""``promotedFrom`` (where a form was copied from: the source workspace's and
form's ids, who copied it, a hash, counts) is staff information. Respondents and
the public never get it, on any read, whatever the switch says; staff keep it.

Every serializer of ``WorkspaceFormSettings`` was checked when the field was added
(the settings of a served form go through ``strip_internal_fields``, the stubs of
``services/form_service.py`` and the settings patch's own DTO). These tests pin the
paths a respondent can reach."""

import datetime as dt
import json

import pytest

from backend.app.container import container
from backend.app.models.workspace import PromotedFrom, WorkspaceFormSettings
from backend.app.models.dtos.settings_patch import SettingsPatchDto
from backend.app.services.internal_fields import strip_internal_fields
from tests.app.controllers.data import testUser
from tests.app.form_access.helpers import cookies
from tests.app.form_promotion.helpers import create_source, url

pytestmark = pytest.mark.asyncio

API = "/api/v1"
SOURCE_WORKSPACE = "a1" * 12
SOURCE_FORM = "b2" * 12
BY = "c3" * 12
# what must not appear anywhere in what a respondent gets: the ids and the hash
# (the key itself comes back as null, like the other staff-only settings)
TELL_TALES = (SOURCE_WORKSPACE, SOURCE_FORM, BY, "d4" * 8, "source_hash", "sourceHash")


def mark() -> PromotedFrom:
    return PromotedFrom(
        workspace_id=SOURCE_WORKSPACE,
        form_id=SOURCE_FORM,
        at=dt.datetime(2026, 11, 2, tzinfo=dt.timezone.utc),
        by=BY,
        source_hash="d4" * 8,
        not_carried={"webhooks": 2},
        adjusted={"imagesDropped": 1},
    )


@pytest.fixture(autouse=True)
def no_member_names(monkeypatch):
    """The auth service is not there: names are best effort and absent."""

    async def get(self, url, **kwargs):
        raise ConnectionError("no auth service in tests")

    monkeypatch.setattr(type(container.http_client()), "get", get)


@pytest.fixture()
async def published(workspace):
    """A published form whose link carries the mark."""
    form_id, _ = await create_source(workspace)
    await container.workspace_form_service().publish_form(
        workspace.id, form_id, testUser
    )
    await container.workspace_form_repo().set_promoted_from(
        workspace.id, form_id, mark()
    )
    return form_id


def clean(response, what: str) -> None:
    assert response.status_code == 200, (what, response.status_code, response.text)
    text = response.text
    for tale in TELL_TALES:
        assert tale not in text, (what, tale)
    assert not filled(response.json()), what


def filled(node) -> bool:
    """Whether a key ``promotedFrom`` / ``promoted_from`` holds anything, anywhere."""
    if isinstance(node, dict):
        return any(
            (key in ("promotedFrom", "promoted_from") and value is not None)
            or filled(value)
            for key, value in node.items()
        )
    if isinstance(node, list):
        return any(filled(item) for item in node)
    return False


async def link_settings(workspace, form_id, **changes):
    repo = container.workspace_form_repo()
    link = await repo.find_workspace_form(workspace.id, form_id)
    for key, value in changes.items():
        setattr(link.settings, key, value)
    await repo.update(link.id, link)


# -- what a respondent reaches -------------------------------------------------------------------
async def test_the_published_form_by_id_and_by_its_link(client, workspace, published):
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, published
    )
    for key in (published, link.settings.custom_url):
        clean(
            await client.get(
                f"{API}/workspaces/{workspace.id}/forms/{key}",
                params={"published": "true"},
            ),
            f"form {key}",
        )


async def test_a_private_form_stub(client, workspace, published):
    await link_settings(workspace, published, private=True)
    response = await client.get(
        f"{API}/workspaces/{workspace.id}/forms/{published}",
        params={"published": "true"},
    )
    clean(response, "private stub")
    assert "welcomePage" in response.json()


async def test_a_hidden_form_stub(client, workspace, published):
    await link_settings(workspace, published, hidden=True)
    clean(
        await client.get(
            f"{API}/workspaces/{workspace.id}/forms/{published}",
            params={"published": "true"},
        ),
        "hidden stub",
    )


async def test_a_closed_form_stub(client, workspace, published):
    await link_settings(
        workspace,
        published,
        form_close_date=dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc),
    )
    response = await client.get(
        f"{API}/workspaces/{workspace.id}/forms/{published}",
        params={"published": "true"},
    )
    clean(response, "closed stub")
    assert response.json().get("unavailable") == "closed"


async def test_a_form_that_is_full_or_not_open_yet_is_a_stub_too(
    client, workspace, published
):
    await link_settings(
        workspace,
        published,
        form_open_date=dt.datetime(2099, 1, 1, tzinfo=dt.timezone.utc),
    )
    response = await client.get(
        f"{API}/workspaces/{workspace.id}/forms/{published}",
        params={"published": "true"},
    )
    clean(response, "not open yet")
    assert response.json().get("unavailable")


async def test_the_public_listing_and_the_search(client, workspace, published):
    listing = await client.get(
        f"{API}/workspaces/{workspace.id}/forms", params={"published": "true"}
    )
    clean(listing, "public listing")
    assert listing.json()["items"], "the published form is listed"
    found = await client.post(
        f"{API}/workspaces/{workspace.id}/forms/search",
        params={"query": "Aanmelding", "published": "true"},
    )
    clean(found, "public search")
    assert found.json()


async def test_the_published_version_read_by_the_public(client, workspace, published):
    clean(
        await client.get(f"{API}/workspaces/{workspace.id}/forms/{published}/versions/1"),
        "version",
    )
    await link_settings(
        workspace,
        published,
        form_close_date=dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc),
    )
    clean(
        await client.get(f"{API}/workspaces/{workspace.id}/forms/{published}/versions/1"),
        "version of a closed form",
    )


# -- what staff keep ------------------------------------------------------------------------------------
async def test_staff_read_where_the_form_came_from(
    client, workspace, published, mock_aiohttp_get_request
):
    with mock_aiohttp_get_request:
        response = await client.get(
            f"{API}/workspaces/{workspace.id}/forms/{published}",
            cookies=cookies(testUser),
        )
        assert response.status_code == 200, response.text
        came = response.json()["settings"]["promotedFrom"]
        assert (came["workspaceId"], came["formId"]) == (SOURCE_WORKSPACE, SOURCE_FORM)
        assert came["notCarried"] == {"webhooks": 2}
        # the staff listing too
        listing = await client.get(
            f"{API}/workspaces/{workspace.id}/forms", cookies=cookies(testUser)
        )
        assert listing.status_code == 200, listing.text
        first = listing.json()["items"][0]["settings"]["promotedFrom"]
        assert first["formId"] == SOURCE_FORM


# -- the helpers, directly ------------------------------------------------------------------------------
def test_the_strip_removes_it_from_a_model_and_from_a_dict_in_either_spelling():
    from fastapi_camelcase import CamelModel

    class Served(CamelModel):
        settings: WorkspaceFormSettings

    model = Served(settings=WorkspaceFormSettings(promoted_from=mark()))
    assert strip_internal_fields(model).settings.promoted_from is None
    for key in ("promoted_from", "promotedFrom"):
        served = {"settings": {key: {"workspaceId": SOURCE_WORKSPACE}, "pinned": True}}
        assert strip_internal_fields(served) == {
            "settings": {key: None, "pinned": True}
        }


def test_no_input_sets_it():
    """The settings patch has no such field, and unknown keys are refused or
    ignored, never stored."""
    assert "promoted_from" not in SettingsPatchDto.model_fields
    patch = SettingsPatchDto(**{"promotedFrom": {"workspaceId": "x"}, "purpose": "y"})
    assert getattr(patch, "promoted_from", None) is None
    assert json.loads(patch.model_dump_json(exclude_none=True)) == {"purpose": "y"} or (
        "promoted" not in patch.model_dump_json()
    )


async def test_the_settings_patch_cannot_write_it(client, workspace, published):
    await container.workspace_form_repo().set_promoted_from(
        workspace.id, published, None
    )
    response = await client.patch(
        f"{API}/workspaces/{workspace.id}/forms/{published}/settings",
        json={"promotedFrom": {"workspaceId": SOURCE_WORKSPACE, "formId": SOURCE_FORM}},
        cookies=cookies(testUser),
    )
    assert response.status_code in (200, 422), response.text
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, published
    )
    assert link.settings.promoted_from is None


async def test_the_stored_mark_is_ids_hashes_and_counts_only(workspace, published):
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, published
    )
    stored = link.settings.promoted_from.model_dump(mode="json", by_alias=True)
    assert set(stored) == {
        "workspaceId",
        "formId",
        "at",
        "by",
        "sourceHash",
        "notCarried",
        "adjusted",
    }
