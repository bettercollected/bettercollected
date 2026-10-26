"""A template's retention period (settings.responseExpirationType /
responseExpiration): checked as a form's is when a template is written, kept
by an update that leaves it out, and carried from a form saved as a template."""

import json

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas.template import FormTemplateDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from common.ids import RecordId
from common.models.consent import ResponseRetentionType

pytestmark = pytest.mark.asyncio


def _body(**settings) -> dict:
    return {"template_body": json.dumps({"title": "T", "settings": settings})}


async def _stored(template_id) -> FormTemplateDocument:
    return await container.form_template_repo().get_template_by_id(RecordId(template_id))


@pytest.fixture()
async def own_template(workspace: WorkspaceDocument) -> FormTemplateDocument:
    template = FormTemplateDocument(
        title="Own",
        settings={
            "is_public": True,
            "language": "nl",
            "response_expiration_type": "days",
            "response_expiration": "90",
        },
    )
    template.workspace_id = workspace.id
    return await container.form_template_repo().save(template)


@pytest.mark.parametrize(
    "settings",
    [
        {"responseExpirationType": "days", "responseExpiration": "abc"},
        {"responseExpirationType": "days", "responseExpiration": "0"},
        {"responseExpirationType": "days", "responseExpiration": "99999"},
        {"responseExpirationType": "date", "responseExpiration": "2001-01-01"},
        {"responseExpirationType": "sometimes", "responseExpiration": "5"},
        {"responseExpiration": "30"},
    ],
)
async def test_a_new_template_with_an_unusable_period_is_refused(
    client: AsyncClient, workspace: WorkspaceDocument, test_user_cookies, settings
):
    before = await container.form_template_repo().get_templates_with_creator(
        workspace_id=workspace.id
    )
    response = await client.post(
        f"/api/v1/workspaces/{workspace.id}/template",
        cookies=test_user_cookies,
        data=_body(**settings),
    )
    assert response.status_code == 422, response.text
    after = await container.form_template_repo().get_templates_with_creator(
        workspace_id=workspace.id
    )
    assert len(after) == len(before)


async def test_a_new_template_keeps_a_valid_period_normalised(
    client: AsyncClient, workspace: WorkspaceDocument, test_user_cookies
):
    response = await client.post(
        f"/api/v1/workspaces/{workspace.id}/template",
        cookies=test_user_cookies,
        data=_body(responseExpirationType="days", responseExpiration=" 045 "),
    )
    assert response.status_code == 200, response.text
    stored = await _stored(response.json()["id"])
    assert stored.settings.response_expiration_type == ResponseRetentionType.DAYS
    assert stored.settings.response_expiration == "45"


async def test_an_update_with_an_unusable_period_is_refused_and_changes_nothing(
    client: AsyncClient, workspace, test_user_cookies, own_template
):
    response = await client.patch(
        f"/api/v1/workspaces/{workspace.id}/template/{own_template.id}",
        cookies=test_user_cookies,
        data=_body(responseExpiration="soon"),
    )
    assert response.status_code == 422, response.text
    stored = await _stored(own_template.id)
    assert stored.title == "Own" and stored.settings.response_expiration == "90"


async def test_an_update_that_leaves_the_settings_out_keeps_them(
    client: AsyncClient, workspace, test_user_cookies, own_template
):
    for body in ({"title": "Renamed"}, {"title": "Renamed", "settings": {}}):
        response = await client.patch(
            f"/api/v1/workspaces/{workspace.id}/template/{own_template.id}",
            cookies=test_user_cookies,
            data={"template_body": json.dumps(body)},
        )
        assert response.status_code == 200, response.text
        settings = (await _stored(own_template.id)).settings
        assert settings.is_public is True and settings.language == "nl"
        assert settings.response_expiration_type == ResponseRetentionType.DAYS
        assert settings.response_expiration == "90"


async def test_an_update_changes_only_the_settings_it_names(
    client: AsyncClient, workspace, test_user_cookies, own_template
):
    response = await client.patch(
        f"/api/v1/workspaces/{workspace.id}/template/{own_template.id}",
        cookies=test_user_cookies,
        data=_body(responseExpiration="120"),
    )
    assert response.status_code == 200, response.text
    settings = (await _stored(own_template.id)).settings
    assert settings.response_expiration == "120"
    assert settings.response_expiration_type == ResponseRetentionType.DAYS
    assert settings.language == "nl" and settings.is_public is True


async def test_an_explicit_null_clears_the_period(
    client: AsyncClient, workspace, test_user_cookies, own_template
):
    response = await client.patch(
        f"/api/v1/workspaces/{workspace.id}/template/{own_template.id}",
        cookies=test_user_cookies,
        data=_body(responseExpirationType=None, responseExpiration=None),
    )
    assert response.status_code == 200, response.text
    settings = (await _stored(own_template.id)).settings
    assert settings.response_expiration_type is None
    assert settings.response_expiration is None
    assert settings.language == "nl"


async def test_a_form_saved_as_a_template_carries_its_period(
    client: AsyncClient,
    workspace: WorkspaceDocument,
    workspace_form,
    test_user_cookies,
):
    repo = container.workspace_form_repo()
    link = await repo.get_workspace_form_in_workspace(
        workspace_id=workspace.id, query=str(workspace_form.form_id)
    )
    link.settings.response_expiration_type = ResponseRetentionType.DAYS
    link.settings.response_expiration = "30"
    await repo.save(link)

    response = await client.post(
        f"/api/v1/workspaces/{workspace.id}/form/{workspace_form.form_id}/template",
        cookies=test_user_cookies,
    )
    assert response.status_code == 200, response.text
    settings = (await _stored(response.json()["id"])).settings
    assert settings.response_expiration_type == ResponseRetentionType.DAYS
    assert settings.response_expiration == "30"

    # ... and a form made from that template keeps it
    created = await client.post(
        f"/api/v1/workspaces/{workspace.id}/template/{response.json()['id']}",
        cookies=test_user_cookies,
    )
    assert created.status_code == 200, created.text
    assert created.json()["settings"]["responseExpiration"] == "30"


async def test_a_form_without_a_period_makes_a_template_without_one(
    client: AsyncClient, workspace: WorkspaceDocument, workspace_form, test_user_cookies
):
    response = await client.post(
        f"/api/v1/workspaces/{workspace.id}/form/{workspace_form.form_id}/template",
        cookies=test_user_cookies,
    )
    settings = (await _stored(response.json()["id"])).settings
    assert settings is None or (
        settings.response_expiration_type is None and settings.response_expiration is None
    )
