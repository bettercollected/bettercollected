"""AI chat with the newer ops and client refs (fake provider): a reply
using them applies, and an invalid one gets the corrective retry."""

import json
from typing import Any, Coroutine

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.services.ai.prompt_builder import OPS_GUIDE
from tests.app.ai_helpers import FakeProvider, enable_ai, use_fake_provider
from tests.app.controllers.test_form_ai_chat import _make_v2


@pytest.fixture()
async def fake_provider(monkeypatch, workspace):
    fake = FakeProvider()
    use_fake_provider(monkeypatch, fake)
    await enable_ai(workspace)
    return fake


BATCH = [
    {
        "op": "add_page",
        "ref": "pets",
        "fields": [{"title": "Do you have pets?", "type": "yes_no", "ref": "has_pets"}],
    },
    {
        "op": "add_field",
        "pageId": "$ref:pets",
        "ref": "names",
        "field": {"title": "Their names", "type": "short_text"},
    },
    {
        "op": "set_field_logic",
        "fieldId": "$ref:names",
        "logic": {
            "action": "SHOW",
            "conditions": [
                {"fieldId": "$ref:has_pets", "comparison": "IS_EQUAL", "value": "Yes"}
            ],
        },
    },
    {"op": "move_page", "pageId": "$ref:pets", "index": 0},
    {
        "op": "set_field_validation",
        "fieldId": "field-1",
        "validation": {"maxLength": 80, "preset": "letters"},
    },
    {"op": "set_question_numbering", "show": True},
]


def _url(workspace, form_id):
    return f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/ai/chat"


def test_the_guide_describes_the_new_ops_and_refs():
    for text in (
        '"op":"move_page"',
        '"op":"set_field_validation"',
        '"op":"set_question_numbering"',
        '"ref":"<short name>"',
        '"$ref:<short name>"',
    ):
        assert text in OPS_GUIDE


async def test_a_reply_with_refs_and_new_ops_applies(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies,
    fake_provider: FakeProvider,
):
    doc = await container.form_repo().get_form_document_by_id(workspace_form.form_id)
    await _make_v2(doc)
    fake_provider.replies = [json.dumps({"reply": "Done.", "ops": BATCH})]
    response = await client.post(
        _url(workspace, workspace_form.form_id),
        cookies=test_user_cookies,
        json={"message": "Ask about pets first"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [r["ok"] for r in body["results"]] == [True] * len(BATCH), body["results"]
    assert len(fake_provider.calls) == 1

    saved = await container.form_repo().get_form_document_by_id(workspace_form.form_id)
    pets, original = saved.fields
    assert pets.id == body["results"][0]["createdId"]
    has_pets, names = pets.properties.fields
    assert names.properties.logic.conditions[0].field_id == has_pets.id
    assert original.properties.fields[0].validations.max_length == 80
    assert all(p.properties.show_question_numbers for p in saved.fields)
    assert "move_page" in fake_provider.calls[0]["system"]


async def test_an_invalid_new_op_gets_the_corrective_retry(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies,
    fake_provider: FakeProvider,
):
    doc = await container.form_repo().get_form_document_by_id(workspace_form.form_id)
    await _make_v2(doc)
    fake_provider.replies = [
        # move_page without its index, and a ref name that is not allowed
        json.dumps(
            {
                "reply": "x",
                "ops": [
                    {"op": "move_page", "pageId": "page-1"},
                    {"op": "add_page", "ref": "$ref:bad"},
                ],
            }
        ),
        json.dumps(
            {
                "reply": "Numbered.",
                "ops": [{"op": "set_question_numbering", "show": True}],
            }
        ),
    ]
    response = await client.post(
        _url(workspace, workspace_form.form_id),
        cookies=test_user_cookies,
        json={"message": "number the questions"},
    )
    assert response.status_code == 200, response.text
    assert len(fake_provider.calls) == 2
    retry = fake_provider.calls[1]["messages"][-1]["content"]
    assert "could not be used" in retry and "index" in retry
    assert response.json()["results"][0]["ok"] is True
