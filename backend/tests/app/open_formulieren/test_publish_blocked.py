"""A form imported from Open Formulieren is not published while its import
still "needs review" (services/publish_checks.py ``review_problem``): every
way of publishing refuses with the existing ``form_not_publishable`` error,
which names the import report, and works again once a person clears the mark."""

import json

import pytest
from httpx import AsyncClient

from common.models.standard_form import (
    StandardFieldProperty,
    StandardForm,
    StandardFormField,
    StandardFormFieldType as T,
)

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.settings_patch import SettingsPatchDto
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.form_import import FormImportDocument, ImportStatus
from backend.app.services.publish_checks import FORM_NOT_PUBLISHABLE, NEEDS_REVIEW
from backend.config import settings
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import invited_user, testUser
from tests.app.controllers.test_mcp_server import _call_tool, _make_key
from tests.app.controllers.test_public_api import BASE, _auth, _create, _token

pytestmark = pytest.mark.asyncio


@pytest.fixture()
def import_on(monkeypatch):
    monkeypatch.setattr(settings.open_formulieren, "IMPORT", "on")


def _form() -> StandardForm:
    return StandardForm(
        title="Imported form",
        fields=[
            StandardFormField(
                id="page-1",
                type=T.SLIDE,
                properties=StandardFieldProperty(
                    fields=[
                        StandardFormField(
                            id="q",
                            type=T.SHORT_TEXT,
                            title="Your name",
                            properties=StandardFieldProperty(fields=[]),
                        )
                    ]
                ),
            )
        ],
    )


async def _draft(workspace) -> str:
    form = await container.workspace_form_service().create_form(
        workspace.id, _form(), testUser
    )
    return form.form_id


async def _mark(workspace, form_id: str, record=None) -> FormImportDocument:
    """What the import leaves on a draft: the record and the mark."""
    record = record or await container.form_import_repo().save(
        FormImportDocument(
            workspace_id=workspace.id,
            form_id=form_id,
            created_by=str(testUser.id),
            status=ImportStatus.COMPLETED,
            source_kind="open_formulieren",
            file_name="export.zip",
            content_type="application/zip",
            size_bytes=1,
            sha256="0" * 64,
            source_key="",
            report={"needsReview": True, "items": [{"label": "SECRET LABEL"}]},
        )
    )
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, form_id
    )
    link.settings.needs_review = True
    link.settings.import_source = "open_formulieren"
    link.settings.import_id = str(record.id)
    await container.workspace_form_repo().update(str(link.id), link)
    return record


async def _review(client, workspace, import_id, cookies, reviewed=True):
    return await client.post(
        f"/api/v1/workspaces/{workspace.id}/open-formulieren-imports/{import_id}/review",
        json={"reviewed": reviewed},
        cookies=cookies,
    )


def _only_problem(content) -> dict:
    assert content["code"] == FORM_NOT_PUBLISHABLE
    assert [p["code"] for p in content["problems"]] == [NEEDS_REVIEW]
    return content["problems"][0]


async def _latest(form_id):
    return await container.form_repo().get_latest_version_of_form(form_id)


# ------------------------------------------------------------ the service


async def test_the_service_refuses_while_marked_and_publishes_once_cleared(
    client, workspace, test_user_cookies, import_on
):
    form_id = await _draft(workspace)
    record = await _mark(workspace, form_id)
    with pytest.raises(HTTPException) as raised:
        await container.workspace_form_service().publish_form(
            workspace.id, form_id, testUser
        )
    assert raised.value.status_code == 422
    problem = _only_problem(raised.value.content)
    # the error names the report by id; nothing of its content is in it
    assert problem["importId"] == str(record.id)
    assert "SECRET LABEL" not in str(raised.value.content)
    assert await _latest(form_id) is None

    assert (await _review(client, workspace, record.id, test_user_cookies)).status_code == 200
    published = await container.workspace_form_service().publish_form(
        workspace.id, form_id, testUser
    )
    assert published.version == 1


async def test_the_mark_comes_with_the_other_publish_problems(workspace, import_on):
    form_id = await _draft(workspace)
    draft = await container.form_service().get_form_document_by_id(form_id)
    draft.fields[0].properties.fields[0].type = T.EMAIL  # no "why we ask"
    await container.form_service().update_form(form_id=form_id, form=draft)
    await _mark(workspace, form_id)
    with pytest.raises(HTTPException) as raised:
        await container.workspace_form_service().publish_form(
            workspace.id, form_id, testUser
        )
    codes = [p["code"] for p in raised.value.content["problems"]]
    assert codes[0] == NEEDS_REVIEW and len(codes) == 2


async def test_marking_it_again_blocks_again(client, workspace, test_user_cookies, import_on):
    form_id = await _draft(workspace)
    record = await _mark(workspace, form_id)
    await _review(client, workspace, record.id, test_user_cookies)
    await _review(client, workspace, record.id, test_user_cookies, reviewed=False)
    with pytest.raises(HTTPException):
        await container.workspace_form_service().publish_form(
            workspace.id, form_id, testUser
        )


async def test_outside_the_switch_the_review_call_only_clears(
    client, workspace, test_user_cookies, monkeypatch
):
    form_id = await _draft(workspace)
    monkeypatch.setattr(settings.open_formulieren, "IMPORT", "on")
    record = await _mark(workspace, form_id)
    monkeypatch.setattr(settings.open_formulieren, "IMPORT", "off")
    # re-marking answers 410 like the rest of the import, and changes nothing
    again = await _review(client, workspace, record.id, test_user_cookies, reviewed=False)
    assert again.status_code == 410 and again.json()["code"] == "open_formulieren_off"
    link = await container.workspace_form_repo().find_workspace_form(workspace.id, form_id)
    assert link.settings.needs_review is True
    assert (await _review(client, workspace, record.id, test_user_cookies)).status_code == 200
    # on again: marking again works, as before
    monkeypatch.setattr(settings.open_formulieren, "IMPORT", "on")
    back = await _review(client, workspace, record.id, test_user_cookies, reviewed=False)
    assert back.status_code == 200 and back.json()["needsReview"] is True
    link = await container.workspace_form_repo().find_workspace_form(workspace.id, form_id)
    assert link.settings.needs_review is True


async def test_clearing_the_mark_keeps_a_settings_change_made_meanwhile(workspace):
    """The mark is written alone: a stale copy of the link read before a
    settings change does not bring the old settings back."""
    form_id = await _draft(workspace)
    record = await _mark(workspace, form_id)
    repo = container.workspace_form_repo()
    stale = await repo.find_workspace_form(workspace.id, form_id)
    assert stale.settings.pinned is not True
    await container.form_service().patch_settings_in_workspace_form(
        workspace.id, form_id, SettingsPatchDto(pinned=True), testUser
    )
    named = await repo.set_review_mark_by_import(workspace.id, str(record.id), False)
    assert named == 1
    link = await repo.find_workspace_form(workspace.id, form_id)
    assert (link.settings.needs_review, link.settings.pinned) == (False, True)
    # a form already clear is not written again
    assert await repo.set_review_mark_by_import(workspace.id, str(record.id), False) == 1
    # another workspace's forms are never named
    assert await repo.set_review_mark_by_import(workspace.id, "6720a0c1e4b0c8a5f1d2e3f4", False) == 0


async def test_an_unmarked_form_publishes_as_before(workspace, import_on):
    form_id = await _draft(workspace)
    published = await container.workspace_form_service().publish_form(
        workspace.id, form_id, testUser
    )
    assert published.version == 1


# --------------------------------------------------- every way to publish


async def test_the_builder_endpoint_refuses_then_publishes(
    client: AsyncClient, workspace, test_user_cookies, import_on
):
    form_id = await _draft(workspace)
    record = await _mark(workspace, form_id)
    path = f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/publish"
    response = await client.post(path, cookies=test_user_cookies)
    assert response.status_code == 422
    assert _only_problem(response.json())["importId"] == str(record.id)
    assert await _latest(form_id) is None

    await _review(client, workspace, record.id, test_user_cookies)
    assert (await client.post(path, cookies=test_user_cookies)).status_code == 200


async def test_the_public_api_refuses_then_publishes(
    client: AsyncClient, workspace, test_user_cookies, import_on
):
    token = await _token(workspace.id)
    form_id = (await _create(client, token)).json()["formId"]
    record = await _mark(workspace, form_id)
    path = f"{BASE}/forms/{form_id}/publish"
    response = await client.post(path, headers=_auth(token))
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == FORM_NOT_PUBLISHABLE
    assert "still needs review" in body["message"]
    assert "SECRET LABEL" not in response.text
    assert await _latest(form_id) is None

    await _review(client, workspace, record.id, test_user_cookies)
    assert (await client.post(path, headers=_auth(token))).status_code == 200


async def test_the_mcp_server_refuses_then_publishes(
    client: AsyncClient, workspace, test_user_cookies, import_on
):
    form_id = await _draft(workspace)
    record = await _mark(workspace, form_id)
    token = await _make_key(workspace.id, ["forms:write"])
    result = await _call_tool(client, token, "publish_form", {"form_id": str(form_id)})
    assert result.get("isError") is True, result
    assert NEEDS_REVIEW in result["content"][0]["text"]
    assert str(record.id) not in result["content"][0]["text"]
    assert await _latest(form_id) is None

    await _review(client, workspace, record.id, test_user_cookies)
    result = await _call_tool(client, token, "publish_form", {"form_id": str(form_id)})
    assert not result.get("isError"), result


async def test_the_spec_writer_refuses(workspace, import_on):
    form_id = await _draft(workspace)
    await _mark(workspace, form_id)
    with pytest.raises(HTTPException) as raised:
        await container.form_spec_writer().publish(workspace.id, form_id, testUser)
    _only_problem(raised.value.content)
    assert await _latest(form_id) is None


async def test_no_settings_update_clears_or_bypasses_the_mark(
    client: AsyncClient, workspace, test_user_cookies, import_on
):
    """The mark is not a setting a caller can send: a settings patch and a
    whole-form save leave it, and publishing still refuses."""
    form_id = await _draft(workspace)
    record = await _mark(workspace, form_id)
    base = f"/api/v1/workspaces/{workspace.id}/forms/{form_id}"
    patched = await client.patch(
        f"{base}/settings",
        json={"needsReview": False, "importId": "x", "private": False, "pinned": True},
        cookies=test_user_cookies,
    )
    assert patched.status_code in (200, 204, 422), patched.text
    draft = await container.form_service().get_form_document_by_id(form_id)
    body = StandardForm(**draft.model_dump(mode="json")).model_dump(
        mode="json", by_alias=True
    )
    body["settings"] = {"needsReview": False, "importSource": None, "importId": None}
    saved = await client.patch(
        base, data={"form_body": json.dumps(body)}, cookies=test_user_cookies
    )
    # the save itself goes through (so the check below is about the mark, not
    # a refused request) and ignores the mark in what was sent
    assert saved.status_code == 200, saved.text
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, form_id
    )
    assert (link.settings.needs_review, link.settings.import_id) == (True, str(record.id))
    response = await client.post(f"{base}/publish", cookies=test_user_cookies)
    assert response.status_code == 422
    assert await _latest(form_id) is None


# ------------------------------------------------------------- copies


async def test_a_copy_carries_the_mark_and_clearing_the_import_clears_it(
    client, workspace, test_user_cookies, import_on
):
    form_id = await _draft(workspace)
    record = await _mark(workspace, form_id)
    copy = await container.workspace_form_service().duplicate_form(
        workspace.id, form_id, testUser
    )
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, copy.form_id
    )
    assert (link.settings.needs_review, link.settings.import_id) == (True, str(record.id))
    with pytest.raises(HTTPException) as raised:
        await container.workspace_form_service().publish_form(
            workspace.id, copy.form_id, testUser
        )
    assert _only_problem(raised.value.content)["importId"] == str(record.id)

    await _review(client, workspace, record.id, test_user_cookies)
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, copy.form_id
    )
    assert link.settings.needs_review is False
    published = await container.workspace_form_service().publish_form(
        workspace.id, copy.form_id, testUser
    )
    assert published.version == 1


async def test_a_copy_of_a_reviewed_import_is_not_marked(
    client, workspace, test_user_cookies, import_on
):
    form_id = await _draft(workspace)
    record = await _mark(workspace, form_id)
    await _review(client, workspace, record.id, test_user_cookies)
    copy = await container.workspace_form_service().duplicate_form(
        workspace.id, form_id, testUser
    )
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, copy.form_id
    )
    assert not link.settings.needs_review


async def test_a_copy_whose_report_is_gone_is_still_held_and_can_be_cleared(
    client, workspace, test_user_cookies, import_on
):
    form_id = await _draft(workspace)
    record = await _mark(workspace, form_id)
    copy = await container.workspace_form_service().duplicate_form(
        workspace.id, form_id, testUser
    )
    # the original is deleted: its report goes with it
    await container.form_import_repo().delete_by_form_ids([form_id])
    assert await container.form_import_repo().get(record.id) is None
    with pytest.raises(HTTPException) as raised:
        await container.workspace_form_service().publish_form(
            workspace.id, copy.form_id, testUser
        )
    assert _only_problem(raised.value.content)["importId"] == str(record.id)

    # the report cannot be read, but the mark can still be cleared
    assert (
        await client.get(
            f"/api/v1/workspaces/{workspace.id}/open-formulieren-imports/{record.id}",
            cookies=test_user_cookies,
        )
    ).status_code == 404
    cleared = await _review(client, workspace, record.id, test_user_cookies)
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["needsReview"] is False
    assert cleared.json()["status"] == "removed" and cleared.json()["formId"] is None
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, copy.form_id
    )
    assert link.settings.needs_review is False
    published = await container.workspace_form_service().publish_form(
        workspace.id, copy.form_id, testUser
    )
    assert published.version == 1


async def test_a_gone_report_cannot_be_marked_again_or_cleared_by_a_stranger(
    client, workspace, workspace_1, test_user_cookies, test_user_cookies_1, import_on
):
    form_id = await _draft(workspace)
    record = await _mark(workspace, form_id)
    copy = await container.workspace_form_service().duplicate_form(
        workspace.id, form_id, testUser
    )
    await container.form_import_repo().delete_by_form_ids([form_id])
    # only clearing is possible without a report
    assert (
        await _review(client, workspace, record.id, test_user_cookies, reviewed=False)
    ).status_code == 404
    # another workspace's owner finds nothing of this one's, and clears nothing
    other = await _review(client, workspace_1, record.id, test_user_cookies_1)
    assert other.status_code == 404 and other.json()["code"] == "import_not_found"
    # a made-up id clears nothing either
    made_up = await _review(client, workspace, "6720a0c1e4b0c8a5f1d2e3f4", test_user_cookies)
    assert made_up.status_code == 404
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, copy.form_id
    )
    assert link.settings.needs_review is True


# -------------------------------------------------- switch and permissions


async def test_with_the_import_switched_off_the_mark_still_holds_and_can_be_cleared(
    client, workspace, test_user_cookies
):
    assert settings.open_formulieren.IMPORT == "off"
    form_id = await _draft(workspace)
    record = await _mark(workspace, form_id)
    copy = await container.workspace_form_service().duplicate_form(
        workspace.id, form_id, testUser
    )
    for target in (form_id, copy.form_id):
        with pytest.raises(HTTPException) as raised:
            await container.workspace_form_service().publish_form(
                workspace.id, target, testUser
            )
        assert _only_problem(raised.value.content)["importId"] == str(record.id)
    # the report itself stays off (410); the review does not
    get = await client.get(
        f"/api/v1/workspaces/{workspace.id}/open-formulieren-imports/{record.id}",
        cookies=test_user_cookies,
    )
    assert get.status_code == 410
    cleared = await _review(client, workspace, record.id, test_user_cookies)
    assert cleared.status_code == 200, cleared.text
    for target in (form_id, copy.form_id):
        published = await container.workspace_form_service().publish_form(
            workspace.id, target, testUser
        )
        assert published.version == 1


async def test_a_review_with_the_switch_off_keeps_its_permission(
    client, workspace, workspace_1, test_user_cookies_1
):
    form_id = await _draft(workspace)
    record = await _mark(workspace, form_id)
    link = await container.workspace_user_repo().find_workspace_user(
        workspace.id, invited_user.id
    )
    link.roles = [WorkspaceRoles.VIEWER]
    await container.workspace_user_repo().save(link)
    token = access_token(invited_user)
    viewer = {"Authorization": token, "RefreshToken": token}
    assert (await _review(client, workspace, record.id, viewer)).status_code == 403
    assert (await _review(client, workspace, record.id, None)).status_code in (401, 403)
    # a member of another workspace: not found (their own workspace has no such import)
    assert (
        await _review(client, workspace_1, record.id, test_user_cookies_1)
    ).status_code == 404
    linked = await container.workspace_form_repo().find_workspace_form(
        workspace.id, form_id
    )
    assert linked.settings.needs_review is True


async def test_publishing_still_needs_form_edit(
    client: AsyncClient, workspace, import_on
):
    """Permissions are unchanged: a viewer is refused (403), not told about
    the mark."""
    form_id = await _draft(workspace)
    await _mark(workspace, form_id)
    link = await container.workspace_user_repo().find_workspace_user(
        workspace.id, invited_user.id
    )
    link.roles = [WorkspaceRoles.VIEWER]
    await container.workspace_user_repo().save(link)
    token = access_token(invited_user)
    response = await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/publish",
        cookies={"Authorization": token, "RefreshToken": token},
    )
    assert response.status_code == 403
    assert "importId" not in response.text


async def test_clearing_the_mark_keeps_its_permission(
    client, workspace, test_user_cookies, import_on
):
    form_id = await _draft(workspace)
    record = await _mark(workspace, form_id)
    link = await container.workspace_user_repo().find_workspace_user(
        workspace.id, invited_user.id
    )
    link.roles = [WorkspaceRoles.VIEWER]
    await container.workspace_user_repo().save(link)
    token = access_token(invited_user)
    viewer = {"Authorization": token, "RefreshToken": token}
    assert (await _review(client, workspace, record.id, viewer)).status_code == 403


# ---------------------------------------------------------- templates


async def _templates(workspace) -> int:
    repo = container.form_template_repo()
    total = 0
    for v2 in (True, False):
        total += len(
            await repo.get_templates_with_creator(v2=v2, workspace_id=workspace.id)
        )
    return total


def _template_path(workspace, form_id) -> str:
    return f"/api/v1/workspaces/{workspace.id}/form/{form_id}/template"


def _template_refusal(content) -> dict:
    """The refusal of a template: ``needs_review`` with the problem shape of a
    refused publish (same ``importId``), and nothing of the report."""
    assert content["code"] == NEEDS_REVIEW
    assert [p["code"] for p in content["problems"]] == [NEEDS_REVIEW]
    assert "SECRET LABEL" not in str(content)
    return content["problems"][0]


async def test_the_template_endpoint_refuses_while_marked_then_works_once_cleared(
    client: AsyncClient, workspace, test_user_cookies, import_on
):
    form_id = await _draft(workspace)
    record = await _mark(workspace, form_id)
    before = await _templates(workspace)
    path = _template_path(workspace, form_id)

    response = await client.post(path, cookies=test_user_cookies)
    assert response.status_code == 422, response.text
    assert _template_refusal(response.json())["importId"] == str(record.id)
    assert "template" in response.json()["message"]
    assert await _templates(workspace) == before

    assert (await _review(client, workspace, record.id, test_user_cookies)).status_code == 200
    made = await client.post(path, cookies=test_user_cookies)
    assert made.status_code == 200, made.text
    assert await _templates(workspace) == before + 1


async def test_the_service_refuses_a_template_while_marked(workspace, import_on):
    form_id = await _draft(workspace)
    record = await _mark(workspace, form_id)
    before = await _templates(workspace)
    with pytest.raises(HTTPException) as raised:
        await container.workspace_form_service().duplicate_form(
            workspace.id, form_id, testUser, is_template=True
        )
    assert raised.value.status_code == 422
    assert _template_refusal(raised.value.content)["importId"] == str(record.id)
    assert await _templates(workspace) == before


async def test_a_template_stays_refused_with_the_switch_off_and_works_after_clearing(
    client, workspace, test_user_cookies
):
    """The mark alone decides, as for publishing: the import switch is not
    consulted, and the review call clears it whether or not it is on."""
    assert settings.open_formulieren.IMPORT == "off"
    form_id = await _draft(workspace)
    record = await _mark(workspace, form_id)
    path = _template_path(workspace, form_id)
    assert (await client.post(path, cookies=test_user_cookies)).status_code == 422
    assert (await _review(client, workspace, record.id, test_user_cookies)).status_code == 200
    assert (await client.post(path, cookies=test_user_cookies)).status_code == 200


async def test_a_copy_of_a_marked_form_is_refused_as_a_template_too(
    client, workspace, test_user_cookies, import_on
):
    form_id = await _draft(workspace)
    record = await _mark(workspace, form_id)
    copy = await container.workspace_form_service().duplicate_form(
        workspace.id, form_id, testUser
    )
    path = _template_path(workspace, copy.form_id)
    refused = await client.post(path, cookies=test_user_cookies)
    assert refused.status_code == 422
    assert _template_refusal(refused.json())["importId"] == str(record.id)
    # clearing the import clears the copy's mark with it
    await _review(client, workspace, record.id, test_user_cookies)
    assert (await client.post(path, cookies=test_user_cookies)).status_code == 200


async def test_a_normal_duplicate_of_a_marked_form_still_works_and_keeps_the_mark(
    client, workspace, test_user_cookies, import_on
):
    form_id = await _draft(workspace)
    record = await _mark(workspace, form_id)
    before = await _templates(workspace)
    response = await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/duplicate",
        cookies=test_user_cookies,
    )
    assert response.status_code == 200, response.text
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, response.json()["formId"]
    )
    assert (link.settings.needs_review, link.settings.import_id) == (True, str(record.id))
    assert await _templates(workspace) == before


async def test_a_template_from_an_unmarked_or_reviewed_form_is_made_as_before(
    client, workspace, test_user_cookies, import_on
):
    plain = await _draft(workspace)
    assert (
        await client.post(_template_path(workspace, plain), cookies=test_user_cookies)
    ).status_code == 200
    reviewed = await _draft(workspace)
    record = await _mark(workspace, reviewed)
    await _review(client, workspace, record.id, test_user_cookies)
    assert (
        await client.post(_template_path(workspace, reviewed), cookies=test_user_cookies)
    ).status_code == 200


async def test_a_template_needs_form_create_before_the_mark_is_mentioned(
    client: AsyncClient, workspace, import_on
):
    """Permissions are unchanged: a viewer is refused (403), not told about
    the mark."""
    form_id = await _draft(workspace)
    await _mark(workspace, form_id)
    link = await container.workspace_user_repo().find_workspace_user(
        workspace.id, invited_user.id
    )
    link.roles = [WorkspaceRoles.VIEWER]
    await container.workspace_user_repo().save(link)
    token = access_token(invited_user)
    response = await client.post(
        _template_path(workspace, form_id),
        cookies={"Authorization": token, "RefreshToken": token},
    )
    assert response.status_code == 403
    assert "importId" not in response.text
