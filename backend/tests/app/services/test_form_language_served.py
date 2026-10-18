"""A form's declared language reaches the builder and the respondent page.

The language is kept on the form (``StandardFormSettings.language``), while
a form is returned with its workspace association's settings. The read
carries the form's language along with them, on the draft read, the
published read and the stub a private form's visitors get, so the
respondent page can mark the form's own text with it and the builder's
plain-language hints know which language to check."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.services.form_service import FormService
from tests.app.controllers.data import testUser


@pytest.fixture()
def user_details():
    """The draft read asks the auth service for the importer's details."""
    with patch.object(
        FormService,
        "fetch_user_details",
        AsyncMock(return_value={"users_info": [{"_id": testUser.id}]}),
    ):
        yield


def _forms_url(workspace, form_id=""):
    base = f"/api/v1/workspaces/{workspace.id}/forms"
    return f"{base}/{form_id}" if form_id else base


def _body(settings=None):
    body = {
        "title": "Taal",
        "builderVersion": "v2",
        "fields": [
            {
                "id": "page-1",
                "index": 0,
                "type": "slide",
                "properties": {
                    "layout": "SINGLE_COLUMN_NO_BACKGROUND",
                    "fields": [
                        {"id": "naam", "index": 0, "type": "short_text", "title": "Naam"}
                    ],
                },
            }
        ],
        "thankyouPage": [{"layout": "SINGLE_COLUMN_NO_BACKGROUND"}],
    }
    if settings is not None:
        body["settings"] = settings
    return body


async def _save_and_publish(client, workspace, form_id, cookies, settings=None):
    reply = await client.patch(
        _forms_url(workspace, form_id),
        data={"form_body": json.dumps(_body(settings))},
        cookies=cookies,
    )
    assert reply.status_code == 200, reply.text
    await container.workspace_form_service().publish_form(
        workspace.id, form_id, testUser
    )


async def test_the_declared_language_is_served_with_the_form(
    client: AsyncClient, workspace, workspace_form, test_user_cookies, user_details
):
    form_id = workspace_form.form_id
    await _save_and_publish(
        client, workspace, form_id, test_user_cookies, settings={"language": "nl"}
    )

    # The respondent's read (signed out) and the builder's draft read.
    live = await client.get(_forms_url(workspace, form_id), params={"published": True})
    assert live.status_code == 200, live.text
    draft = await client.get(_forms_url(workspace, form_id), cookies=test_user_cookies)
    assert draft.status_code == 200, draft.text

    for reply in (live, draft):
        settings = reply.json()["settings"]
        assert settings["language"] == "nl"
        # Still the association's settings, not the form's own.
        assert settings["customUrl"] == workspace_form.settings.custom_url
        assert settings["private"] is False

    # Kept on the form only: the association does not take it on.
    association = await container.workspace_form_repo().get_workspace_form_in_workspace(
        workspace.id, form_id
    )
    assert "language" not in association.settings.model_dump()


async def test_a_form_without_a_language_serves_none(
    client: AsyncClient, workspace, workspace_form, test_user_cookies
):
    form_id = workspace_form.form_id
    await _save_and_publish(client, workspace, form_id, test_user_cookies)

    live = await client.get(_forms_url(workspace, form_id), params={"published": True})
    assert live.status_code == 200, live.text
    assert live.json()["settings"].get("language") is None


async def test_a_private_form_stub_carries_the_language(
    client: AsyncClient, workspace, workspace_form, test_user_cookies
):
    form_id = workspace_form.form_id
    await _save_and_publish(
        client, workspace, form_id, test_user_cookies, settings={"language": "nl"}
    )
    reply = await client.patch(
        f"{_forms_url(workspace, form_id)}/settings",
        json={"private": True},
        cookies=test_user_cookies,
    )
    assert reply.status_code == 200, reply.text
    # The patch answers about the association, which has no language: it
    # leaves the key out rather than report it empty (the builder keeps its own).
    assert "language" not in reply.json()["settings"]

    stub = await client.get(_forms_url(workspace, form_id), params={"published": True})
    assert stub.status_code == 200, stub.text
    body = stub.json()
    # The stub: welcome page and settings, no questions.
    assert not body.get("fields")
    assert body["settings"]["private"] is True
    assert body["settings"]["language"] == "nl"
