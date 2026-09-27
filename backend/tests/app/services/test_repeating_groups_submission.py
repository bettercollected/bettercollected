"""Repeating groups end to end through the services: form save, publish,
submission (limits enforced server side) and encrypted storage."""

import pytest
from common.models.standard_form import StandardForm

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from tests.app.controllers.data import testUser

pytestmark = pytest.mark.asyncio

GROUP = {
    "id": "applicants",
    "type": "group",
    "title": "Applicants",
    "properties": {
        "repeat": {"minItems": 1, "maxItems": 2, "itemLabel": "Applicant"},
        "fields": [
            {
                "id": "name",
                "type": "short_text",
                "title": "Name",
                "validations": {"required": True},
            },
            {"id": "income", "type": "number", "title": "Income"},
        ],
    },
}


async def _published_group_form(workspace):
    service = container.workspace_form_service()
    form = await service.create_form(
        workspace.id,
        StandardForm(
            builder_version="v2",
            title="Loan application",
            fields=[
                {
                    "id": "s1",
                    "type": "slide",
                    "index": 0,
                    "properties": {"fields": [GROUP]},
                }
            ],
        ),
        testUser,
    )
    await service.publish_form(workspace.id, form.form_id, testUser)
    return form


def _item(name, income=None):
    item = {"name": {"type": "text", "text": name}}
    if income is not None:
        item["income"] = {"type": "number", "number": income}
    return item


async def test_group_answers_are_stored_per_item_and_encrypted(workspace):
    form = await _published_group_form(workspace)
    answers = {
        "applicants": {"type": "group", "items": [_item("Sita", 100), _item("Ram")]}
    }

    response = await container.workspace_form_service().submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(answers=answers),
        testUser,
    )

    stored = await container.form_response_repo().get_response(response.response_id)
    assert isinstance(stored.answers, (bytes, str))
    decrypted = container.form_response_service().decrypt_form_response(
        workspace_id=workspace.id, response=stored
    )
    items = decrypted.answers["applicants"]["items"]
    assert [i["name"]["text"] for i in items] == ["Sita", "Ram"]
    assert items[0]["income"]["number"] == 100


async def test_submission_over_the_limit_is_rejected(workspace):
    form = await _published_group_form(workspace)
    answers = {
        "applicants": {"type": "group", "items": [_item("A"), _item("B"), _item("C")]}
    }
    with pytest.raises(HTTPException) as error:
        await container.workspace_form_service().submit_response(
            workspace.id,
            form.form_id,
            StandardFormResponseCamelModel(answers=answers),
            testUser,
        )
    assert error.value.status_code == 422
    assert "at most 2" in error.value.content


async def test_submission_missing_a_required_item_answer_is_rejected(workspace):
    form = await _published_group_form(workspace)
    answers = {
        "applicants": {
            "type": "group",
            "items": [{"income": {"type": "number", "number": 5}}],
        }
    }
    with pytest.raises(HTTPException) as error:
        await container.workspace_form_service().submit_response(
            workspace.id,
            form.form_id,
            StandardFormResponseCamelModel(answers=answers),
            testUser,
        )
    assert "Applicant 1" in error.value.content


async def test_saved_form_keeps_repeat_settings(workspace):
    form = await _published_group_form(workspace)
    loaded = await container.form_service().get_form_document_by_id(form.form_id)
    group = loaded.fields[0].properties.fields[0]
    assert group.properties.repeat.max_items == 2
    assert [c.id for c in group.properties.fields] == ["name", "income"]
