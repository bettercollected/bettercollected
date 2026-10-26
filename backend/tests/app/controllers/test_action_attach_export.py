"""Attaching an action to a form (or turning one back on) sends the answers
out on every submission: besides ``form.edit`` it needs ``response.export``.
Today every role with ``form.edit`` holds export too; these tests take
export away from the Editor role to show the second check."""

import pytest
from common.ids import RecordId
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.dtos.action_dto import ActionDto
from backend.app.models.enum.permission import Permission
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.services import authorization_service
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import invited_user, testUser


def _cookies(user):
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


@pytest.fixture()
def editor_without_export(monkeypatch):
    """The Editor role (``invited_user`` is one in ``workspace``) with
    ``form.edit`` but not ``response.export``."""
    monkeypatch.setitem(
        authorization_service.ROLE_PERMISSIONS,
        WorkspaceRoles.EDITOR,
        authorization_service.EDITOR_PERMISSIONS - {Permission.RESPONSE_EXPORT},
    )


@pytest.fixture()
async def action():
    return await container.action_repository().create_global_action(
        ActionDto(name="export_check_action", action_code="", type="external"),
        testUser,
    )


def _url(workspace, workspace_form):
    return f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/actions"


async def test_attaching_needs_export(
    client: AsyncClient, workspace, workspace_form, action, editor_without_export
):
    refused = await client.post(
        _url(workspace, workspace_form),
        json={"action_id": str(action.id)},
        cookies=_cookies(invited_user),
    )
    assert refused.status_code == 403, refused.text
    form = await container.form_repo().get_form_document_by_id(workspace_form.form_id)
    assert not (form.actions or {}).get("on_submit")


async def test_turning_an_action_on_needs_export_but_off_does_not(
    client: AsyncClient, workspace, workspace_form, editor_without_export
):
    url = _url(workspace, workspace_form)
    action_id = str(RecordId())
    enable = await client.patch(
        url,
        json={"actionId": action_id, "updateType": "enable"},
        cookies=_cookies(invited_user),
    )
    assert enable.status_code == 403, enable.text
    disable = await client.patch(
        url,
        json={"actionId": action_id, "updateType": "disable"},
        cookies=_cookies(invited_user),
    )
    assert disable.status_code != 403, disable.text


async def test_an_editor_with_export_still_attaches(
    client: AsyncClient, workspace, workspace_form, action
):
    attached = await client.post(
        _url(workspace, workspace_form),
        json={"action_id": str(action.id)},
        cookies=_cookies(invited_user),
    )
    assert attached.status_code == 200, attached.text
