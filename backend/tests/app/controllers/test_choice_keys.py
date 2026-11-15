"""The ``choiceKeys`` theme key (lettered keys on the answer options): absent or
``letters``, checked by every writer like the other listed theme keys, and
absent leaves a theme as it was. No preset sets it yet. The key is offered while
the Pigment switch is on (test_choice_keys_gate.py): these tests run with it on."""

import json

import pytest
from common.form_spec.models import Theme as SpecTheme
from common.models.standard_form import (
    THEME_CHOICE_KEYS,
    StandardFieldProperty,
    StandardForm,
    StandardFormField,
    StandardFormFieldType as T,
    Theme,
    theme_problems,
)

from backend.app.constants.themes import theme_dict, themes
from backend.app.container import container
from backend.app.models.workspace import WorkspaceThemeDto
from backend.app.services.ai.ops import apply_form_ops, parse_ops
from backend.config import settings

API = "/api/v1"
COLOURS = {
    "title": "Mine",
    "primary": "#1A1238",
    "secondary": "#4B35DB",
    "tertiary": "#7C7396",
    "accent": "#FBF7F1",
}
MESSAGE = "theme.choiceKeys must be one of: letters."


@pytest.fixture(autouse=True)
def pigment_switch_on(monkeypatch):
    monkeypatch.setattr(settings.app_theme, "ENABLED", True)


def _form(theme=None) -> StandardForm:
    return StandardForm(
        title="Form",
        builder_version="v2",
        theme=Theme(**theme) if theme else None,
        fields=[
            StandardFormField(
                id="page-1",
                index=0,
                type=T.SLIDE,
                properties=StandardFieldProperty(
                    fields=[StandardFormField(id="q1", index=0, type=T.SHORT_TEXT, title="Name")]
                ),
            )
        ],
    )


def _body(theme) -> dict:
    page = {"id": "page-1", "index": 0, "type": "slide", "properties": {"fields": []}}
    return {"title": "Themed", "builder_version": "v2", "theme": theme, "fields": [page]}


def test_the_list_has_one_value():
    assert THEME_CHOICE_KEYS == ("letters",)


def test_absent_and_null_and_letters_are_valid_anything_else_is_not():
    assert theme_problems({**COLOURS}) == []
    assert theme_problems({**COLOURS, "choiceKeys": None}) == []
    assert theme_problems({**COLOURS, "choiceKeys": "letters"}) == []
    assert theme_problems({**COLOURS, "choiceKeys": "numbers"}) == [MESSAGE]
    assert theme_problems(Theme(**COLOURS, choiceKeys="letters")) == []


def test_the_spec_and_the_saved_themes_know_it():
    assert SpecTheme.model_validate({**COLOURS, "choiceKeys": "letters"}).choice_keys == "letters"
    with pytest.raises(Exception):
        SpecTheme.model_validate({**COLOURS, "choiceKeys": "numbers"})
    assert WorkspaceThemeDto(**COLOURS, choiceKeys="letters").choiceKeys == "letters"
    assert theme_problems(WorkspaceThemeDto(**COLOURS, choiceKeys="numbers"), "customThemes.0") == [
        "customThemes.0.choiceKeys must be one of: letters."
    ]


def test_only_the_pigment_preset_sets_it():
    assert {name for name, preset in themes.items() if preset.choiceKeys is not None} == {"Pigment"}
    assert {name for name, preset in theme_dict.items() if "choiceKeys" in preset} == {"Pigment"}


def test_update_theme_takes_it_or_refuses_it():
    after, results = apply_form_ops(
        _form(), parse_ops([{"op": "update_theme", "theme": {**COLOURS, "choiceKeys": "letters"}}]), atomic=False
    )
    assert results[0].ok and after.theme.choiceKeys == "letters"
    after, results = apply_form_ops(
        _form(), parse_ops([{"op": "update_theme", "theme": {**COLOURS, "choiceKeys": "numbers"}}]), atomic=False
    )
    assert not results[0].ok and results[0].message == MESSAGE


def test_a_page_theme_is_checked_too():
    ops = parse_ops(
        [{"op": "update_page", "pageId": "page-1", "patch": {"theme": {**COLOURS, "choiceKeys": "numbers"}}}],
        allow_editor_ops=True,
    )
    _, results = apply_form_ops(_form(), ops, atomic=False)
    assert not results[0].ok and results[0].message == MESSAGE


async def test_a_form_save_stores_it_and_refuses_another_value(
    client, workspace, workspace_form, test_user_cookies
):
    url = f"{API}/workspaces/{workspace.id}/forms/{workspace_form.form_id}"
    response = await client.patch(
        url, cookies=test_user_cookies, data={"form_body": json.dumps(_body({**COLOURS, "choiceKeys": "letters"}))}
    )
    assert response.status_code == 200, response.text
    stored = await container.form_service().get_form_document_by_id(workspace_form.form_id)
    assert stored.theme.choiceKeys == "letters"
    response = await client.patch(
        url, cookies=test_user_cookies, data={"form_body": json.dumps(_body({**COLOURS, "choiceKeys": "numbers"}))}
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "theme_not_allowed"
    assert response.json()["message"] == MESSAGE


async def test_saved_themes_take_it_and_refuse_another_value(client, workspace, test_user_cookies):
    url = f"{API}/workspaces/{workspace.id}/theme-presets"
    response = await client.patch(url, cookies=test_user_cookies, json=[{**COLOURS, "choiceKeys": "letters"}])
    assert response.status_code == 200, response.text
    assert response.json()["customThemes"][0]["choiceKeys"] == "letters"
    response = await client.patch(url, cookies=test_user_cookies, json=[{**COLOURS, "choiceKeys": "numbers"}])
    assert response.status_code == 422, response.text
    assert response.json()["message"] == "customThemes.0.choiceKeys must be one of: letters."
