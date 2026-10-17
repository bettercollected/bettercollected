"""A generated yes/no question stores its choices like the builder does:
the fixed values "Yes"/"No" without an English label, so the respondent
form shows them in the respondent's language (a fake provider, never a
real model)."""

from typing import Any, Coroutine

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.services.openai_service import OpenAIService
from tests.app.ai_helpers import FakeProvider, enable_ai, use_fake_provider


@pytest.fixture()
async def fake_provider(monkeypatch, workspace):
    fake = FakeProvider()
    use_fake_provider(monkeypatch, fake)
    await enable_ai(workspace)
    return fake


# A Dutch form as a model returns it; the yes/no question comes without
# choices, or with choices of its own that the converter replaces.
GENERATED_NL = {
    "title": "Aanmelding buurtfeest",
    "description": "Meld je aan voor het buurtfeest.",
    "fields": [
        {
            "title": "Over jou",
            "type": "group",
            "layout": "SINGLE_COLUMN_NO_BACKGROUND",
            "properties": {
                "fields": [
                    {"title": "Je naam", "type": "short_text"},
                    {"title": "Kom je met kinderen?", "type": "yes_no"},
                ]
            },
        },
        {
            "title": "Help je mee met opruimen?",
            "type": "yes_no",
            "layout": "SINGLE_COLUMN_NO_BACKGROUND",
            "properties": {"choices": ["Ja", "Nee"]},
        },
    ],
}


def _yes_no_fields(fields):
    for field in fields or []:
        if str(getattr(field.type, "value", field.type)) == "yes_no":
            yield field
        if field.properties and field.properties.fields:
            yield from _yes_no_fields(field.properties.fields)


def test_the_converter_stores_yes_no_without_labels():
    properties = OpenAIService.convert_properties(
        None, openai_properties={"choices": ["Ja", "Nee"]}, type="yes_no"
    )
    assert [c["value"] for c in properties["choices"]] == ["Yes", "No"]
    assert all("label" not in c for c in properties["choices"])
    assert len({c["id"] for c in properties["choices"]}) == 2


async def test_a_dutch_generated_form_keeps_no_english_yes_no_labels(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    test_user_cookies: dict[str, str],
    fake_provider: FakeProvider,
):
    fake_provider.replies = [GENERATED_NL]
    response = await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/ai",
        cookies=test_user_cookies,
        json={"prompt": "Een aanmeldformulier voor het buurtfeest"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    form_id = body.get("formId") or body["form_id"]

    saved = await container.form_repo().get_form_document_by_id(form_id)
    questions = list(_yes_no_fields(saved.fields))
    assert len(questions) == 2
    for question in questions:
        choices = question.properties.choices
        # the fixed values the respondent form and logic rely on ...
        assert [c.value for c in choices] == ["Yes", "No"]
        # ... and no English text of their own
        assert [c.label for c in choices] == [None, None]
