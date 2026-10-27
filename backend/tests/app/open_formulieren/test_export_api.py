"""The export endpoint: the switch, who may use it, what it answers and what
it never carries."""

import io
import re
import zipfile

import pytest
from common.models.standard_form import StandardForm

from backend.app.container import container
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.services.open_formulieren import exporter
from backend.app.services.open_formulieren.archive import read_archive
from backend.config import settings
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import invited_user, testUser, testUser1, testUser2
from tests.app.open_formulieren.export_helpers import (
    INTERNAL_TITLE,
    entries,
    form_of,
    kitchen_sink,
    q,
    slide,
)

pytestmark = pytest.mark.asyncio

ROOT = "/api/v1"
ANSWER = "Ada-ANSWER-9d2e41"
INTERNAL_ANSWER = "REF-INTERNAL-5c1b77"
HIDDEN_VALUE = "campaign-7f1e"


def url(workspace, form_id):
    return f"{ROOT}/workspaces/{workspace.id}/forms/{form_id}/open-formulieren-export"


def cookies_of(user):
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


@pytest.fixture()
def export_on(monkeypatch):
    monkeypatch.setattr(settings.open_formulieren, "EXPORT", "on")


async def make_form(workspace, form=None, user=testUser):
    created = await container.workspace_form_service().create_form(
        workspace.id, form or kitchen_sink(), user
    )
    return created.form_id


async def make_viewer(workspace):
    link = await container.workspace_user_repo().find_workspace_user(
        workspace.id, invited_user.id
    )
    link.roles = [WorkspaceRoles.VIEWER]
    await container.workspace_user_repo().save(link)
    return cookies_of(invited_user)


# -------------------------------------------------------------- the switch


async def test_it_is_off_by_default_and_answers_before_anything_is_looked_at(
    client, workspace, test_user_cookies
):
    assert settings.open_formulieren.EXPORT == "off"
    form_id = await make_form(workspace)
    for cookies in (test_user_cookies, cookies_of(testUser1), None):
        for target in (form_id, "6720a0c1e4b0c8a5f1d2e3f4"):
            response = await client.get(url(workspace, target), cookies=cookies)
            assert response.status_code == 410, response.text
            assert response.json()["code"] == "open_formulieren_off"
            assert response.headers.get("x-open-formulieren-unmapped") is None


async def test_the_import_switch_does_not_turn_the_export_on(
    client, workspace, test_user_cookies, monkeypatch
):
    monkeypatch.setattr(settings.open_formulieren, "IMPORT", "on")
    form_id = await make_form(workspace)
    response = await client.get(url(workspace, form_id), cookies=test_user_cookies)
    assert response.status_code == 410


async def test_an_unknown_mode_refuses_to_start():
    from pydantic import ValidationError

    from backend.config.open_formulieren_settings import OpenFormulierenSettings

    assert OpenFormulierenSettings(EXPORT=" On ").EXPORT == "on"
    with pytest.raises(ValidationError):
        OpenFormulierenSettings(EXPORT="readonly")


async def test_the_providers_list_offers_it_only_when_on(client, monkeypatch):
    names = lambda r: [p["providerName"] for p in r.json()]  # noqa: E731
    assert "open_formulieren" not in names(await client.get(f"{ROOT}/providers"))
    monkeypatch.setattr(settings.open_formulieren, "EXPORT", "on")
    after = await client.get(f"{ROOT}/providers")
    assert {"providerName": "open_formulieren", "importMode": None, "exportMode": "on"} in after.json()
    monkeypatch.setattr(settings.open_formulieren, "IMPORT", "on")
    both = await client.get(f"{ROOT}/providers")
    assert {
        "providerName": "open_formulieren", "importMode": "on", "exportMode": "on",
    } in both.json()


# ---------------------------------------------------------------- a success


async def test_an_export_is_a_zip_with_the_unmapped_count_in_a_header(
    client, workspace, test_user_cookies, export_on
):
    form_id = await make_form(workspace)
    response = await client.get(url(workspace, form_id), cookies=test_user_cookies)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"] == (
        'attachment; filename="kitchen-sink-open-formulieren.zip"'
    )
    archive = entries(response.content)
    assert list(archive) == list(exporter.EXPORT_ENTRIES)
    readme = archive[exporter.README_ENTRY]
    listed = re.search(r"Items listed: (\d+)", readme).group(1)
    assert response.headers["x-open-formulieren-unmapped"] == listed != "0"
    # the archive passes our own hardened reader
    assert read_archive(response.content).version == "4.0.6"


async def test_the_cors_headers_let_the_webapp_read_the_count_and_the_name(
    client, workspace, test_user_cookies, export_on, monkeypatch
):
    from backend.app.middlewares.dynamic_cors_middleware import DynamicCORSMiddleware

    monkeypatch.setattr(DynamicCORSMiddleware, "_allowed_origins", ["http://admin.test"])
    form_id = await make_form(workspace)
    response = await client.get(
        url(workspace, form_id),
        cookies=test_user_cookies,
        headers={"Origin": "http://admin.test"},
    )
    exposed = response.headers.get("access-control-expose-headers", "").lower()
    assert "x-open-formulieren-unmapped" in exposed and "content-disposition" in exposed


async def test_the_file_name_cannot_carry_anything_but_a_name(
    client, workspace, test_user_cookies, export_on
):
    form_id = await make_form(
        workspace,
        form_of(slide("p", [q("a", "short_text", "A")], "P"), title='Ünï "x" ../../a\r\nSet-Cookie: z=1'),
    )
    response = await client.get(url(workspace, form_id), cookies=test_user_cookies)
    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert re.fullmatch(r'attachment; filename="[a-z0-9-]+-open-formulieren\.zip"', disposition)
    assert "set-cookie" not in response.headers


def publishable() -> StandardForm:
    """A form the publish checks accept (no personal-data questions)."""
    return form_of(
        slide("p1", [
            q("name", "short_text", "Your name"),
            q("bio", "long_text", "About you"),
            q("staff", "short_text", INTERNAL_TITLE, internal=True),
        ], "About you"),
        title="Kitchen sink",
        hidden_fields=["utm_source"],
    )


async def test_the_draft_is_exported_as_it_is_now(client, workspace, test_user_cookies, export_on):
    form_id = await make_form(workspace, publishable())
    await container.workspace_form_service().publish_form(workspace.id, form_id, testUser)
    response = await client.get(url(workspace, form_id), cookies=test_user_cookies)
    assert response.status_code == 200
    assert entries(response.content)["forms.json"][0]["name"] == "Kitchen sink"


async def test_a_form_with_nothing_to_export_is_422(client, workspace, test_user_cookies, export_on):
    form_id = await make_form(
        workspace, form_of(slide("p", [q("a", "short_text", "A", internal=True)], "P"))
    )
    response = await client.get(url(workspace, form_id), cookies=test_user_cookies)
    assert response.status_code == 422
    assert response.json()["code"] == "nothing_to_export"


# -------------------------------------------------- who may and whose form


async def test_a_viewer_who_may_read_forms_may_export_them(client, workspace, export_on):
    form_id = await make_form(workspace)
    cookies = await make_viewer(workspace)
    response = await client.get(url(workspace, form_id), cookies=cookies)
    assert response.status_code == 200


async def test_a_non_member_and_a_signed_out_caller_are_refused(
    client, workspace, export_on
):
    form_id = await make_form(workspace)
    for user in (testUser1, testUser2):
        response = await client.get(url(workspace, form_id), cookies=cookies_of(user))
        assert response.status_code == 403, response.text
        assert b"PK" not in response.content[:2]
    assert (await client.get(url(workspace, form_id))).status_code == 401


async def test_the_form_must_belong_to_the_workspace(
    client, workspace, workspace_1, test_user_cookies, export_on
):
    other_form = await make_form(workspace_1, user=testUser1)
    mine = await make_form(workspace)
    # another workspace's form through mine: not found, nothing leaks
    response = await client.get(url(workspace, other_form), cookies=test_user_cookies)
    assert response.status_code == 404
    # another workspace through my session: not a member
    response = await client.get(url(workspace_1, mine), cookies=test_user_cookies)
    assert response.status_code in (403, 404)
    unknown = await client.get(
        url(workspace, "6720a0c1e4b0c8a5f1d2e3f4"), cookies=test_user_cookies
    )
    assert unknown.status_code == 404


# ----------------------------------------------- never responses, never staff


async def test_no_response_and_no_staff_only_question_is_in_the_archive(
    client, workspace, test_user_cookies, export_on
):
    form_id = await make_form(workspace, publishable())
    await container.workspace_form_service().publish_form(workspace.id, form_id, testUser)
    response = await container.workspace_form_service().submit_response(
        workspace.id,
        form_id,
        StandardFormResponseCamelModel(
            answers={
                "name": {"field": {"id": "name"}, "type": "text", "text": ANSWER},
                "bio": {"field": {"id": "bio"}, "type": "text", "text": f"{ANSWER} bio"},
            },
            hidden_fields={"utm_source": HIDDEN_VALUE},
            anonymize=False,
        ),
        testUser2,
    )
    patched = await client.patch(
        f"{ROOT}/workspaces/{workspace.id}/forms/{form_id}/submissions/"
        f"{response.response_id}/internal-answers",
        json={"answers": {"staff": {"type": "text", "text": INTERNAL_ANSWER}}},
        cookies=test_user_cookies,
    )
    assert patched.status_code == 200, patched.text

    result = await client.get(url(workspace, form_id), cookies=test_user_cookies)
    assert result.status_code == 200
    with zipfile.ZipFile(io.BytesIO(result.content)) as archive:
        everything = b"".join(archive.read(n) for n in archive.namelist())
    for seeded in (ANSWER, INTERNAL_ANSWER, HIDDEN_VALUE, INTERNAL_TITLE, "STAFFONLY", "Office use"):
        assert seeded.encode() not in everything, seeded
    # nor the person who answered, nor who made the form, nor a workspace
    for private in (testUser.id, testUser.sub, testUser2.id, str(workspace.id), "respondent"):
        assert str(private).encode() not in everything, private
    # the form's own structure is there
    assert b"Your name" in everything and b"Kitchen sink" in everything
    assert b"utm_source" not in everything
