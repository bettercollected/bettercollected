"""A mark that says the backend runs a form's built-in action (``migrated_to``)
is set by the move of built-in actions and by nothing a client sends: a form is
created without actions, parameters or secrets, a whole-form save does not read
them, a copy does not carry them."""

import json

import pytest
from common.models.standard_form import ActionState, ParameterValue, StandardForm, Trigger
from httpx import AsyncClient

from backend.app.container import container
from tests.app.controllers.data import testUser
from tests.app.registration.helpers import FIELDS, publish
from tests.app.services.test_form_language_setting import _body, _draft

pytestmark = pytest.mark.asyncio

MARK = {"kind": "sheets", "id": "65b0000000000000000000a1"}
ACTION = "65b0000000000000000000a1"


def with_actions(body: dict) -> dict:
    return {
        **body,
        "actions": {"on_submit": [{"id": ACTION, "enabled": True, "migratedTo": MARK, "migratedAt": "2026-01-01T00:00:00Z"}]},
        "parameters": {ACTION: [{"name": "Google Sheet Id", "value": "1" * 40}]},
        "secrets": {ACTION: [{"name": "Credentials", "value": "plain-text-secret"}]},
    }


async def test_a_form_created_over_the_api_has_no_actions_parameters_or_secrets(
    client: AsyncClient, workspace, test_user_cookies
):
    reply = await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms",
        data={"form_body": json.dumps(with_actions(_body()))},
        cookies=test_user_cookies,
    )
    assert reply.status_code == 200, reply.text
    stored = await _draft(reply.json()["formId"])
    assert not stored.actions and not stored.parameters and not stored.secrets
    assert "plain-text-secret" not in json.dumps(reply.json())


async def test_a_form_created_by_the_service_with_a_mark_has_none_either(workspace):
    form = StandardForm(
        builder_version="v2",
        title="Marked",
        fields=[{"id": "s1", "type": "slide", "index": 0, "properties": {"fields": FIELDS[:1]}}],
        actions={Trigger.on_submit: [ActionState(id=ACTION, enabled=True, migrated_to=MARK)]},
        parameters={ACTION: [ParameterValue(name="Google Sheet Id", value="1" * 40)]},
    )
    created = await container.workspace_form_service().create_form(workspace.id, form, testUser)
    stored = await _draft(created.form_id)
    assert not stored.actions and not stored.parameters


async def test_a_whole_form_save_does_not_read_actions(client: AsyncClient, workspace, test_user_cookies):
    form = await publish(workspace)
    reply = await client.patch(
        f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}",
        data={"form_body": json.dumps(with_actions({"title": "Renamed"}))},
        cookies=test_user_cookies,
    )
    assert reply.status_code == 200, reply.text
    stored = await _draft(form.form_id)
    assert stored.title == "Renamed" and not stored.actions and not stored.secrets


async def test_a_copy_of_a_form_with_a_mark_carries_no_actions(workspace):
    form = await publish(workspace)
    document = await container.form_repo().get_form_document_by_id(form.form_id)
    document.actions = {Trigger.on_submit: [ActionState(id=ACTION, enabled=True, migrated_to=MARK)]}
    await container.form_repo().save_form(document)
    copy = await container.workspace_form_service().duplicate_form(workspace.id, form.form_id, testUser)
    assert not (await _draft(copy.form_id)).actions


async def test_a_form_made_from_a_template_with_a_mark_carries_no_actions(workspace, monkeypatch):

    service = container.form_template_service()
    template = StandardForm(
        builder_version="v2",
        title="Template",
        fields=[{"id": "s1", "type": "slide", "index": 0, "properties": {"fields": FIELDS[:1]}}],
        actions={Trigger.on_submit: [ActionState(id=ACTION, enabled=True, migrated_to=MARK)]},
    )

    async def fake(user, template_id):
        return template

    monkeypatch.setattr(service, "get_template_by_id", fake)
    created = await service.create_form_from_template(workspace.id, "65b0000000000000000000b1", testUser)
    assert not (await _draft(created.form_id)).actions


async def test_the_actions_a_creator_attaches_later_never_come_with_a_mark(workspace):
    from backend.app.models.dtos.action_dto import ActionDto, AddActionToFormDto

    form = await publish(workspace)
    action = await container.action_repository().create_global_action(
        ActionDto(name="partner_sync", action_code="x()", type="internal"), testUser
    )
    await container.form_service().add_action_form(
        form.form_id, AddActionToFormDto(action_id=action.id), action
    )
    (entry,) = (await _draft(form.form_id)).actions[Trigger.on_submit]
    assert entry.migrated_to is None and entry.migrated_at is None
