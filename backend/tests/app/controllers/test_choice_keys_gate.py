"""The ``choiceKeys`` theme key is gated by the one Pigment switch
(``APP_THEME_PIGMENT_ENABLED``, ``settings.app_theme.ENABLED``) on every path
that takes an inline theme, as the Daybreak artwork is by its own.

While the switch is off, a theme that sets ``choiceKeys`` is refused wherever it
comes from: a whole-form save, a new form, the edit operations, the one write
path of the op writers (AI, MCP, public API) and a workspace's saved themes. A
theme the stored value already has (the same path of the form, the same title
among the saved themes) still saves, so a form that wears the keys keeps working
after the switch is turned off. A copy of a form keeps what its source has. The
guide the AI is given never names the key."""

import json
import re
from pathlib import Path

import pytest
from common.models.standard_form import (
    StandardFieldProperty,
    StandardForm,
    StandardFormField,
    StandardFormFieldType as T,
    Theme,
)

from backend.app.constants.themes import (
    GATED_THEME_KEYS,
    offered_theme_keys,
    theme_key_offered,
)
from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.services.ai.ops import apply_form_ops, parse_ops
from backend.app.services.ai.outline_service import outline_system_prompt
from backend.app.services.ai.prompt_builder import ops_guide
from backend.app.services.form_writes import persist_form
from backend.config import settings
from tests.app.controllers.data import testUser

API = "/api/v1"
PLAIN = {
    "title": "Mine",
    "primary": "#1A1238",
    "secondary": "#4B35DB",
    "tertiary": "#7C7396",
    "accent": "#FBF7F1",
}
KEYED = {**PLAIN, "choiceKeys": "letters"}
REFUSED = "choiceKeys is not available yet."


def _page(theme=None):
    properties = StandardFieldProperty(
        fields=[StandardFormField(id="q1", index=0, type=T.SHORT_TEXT, title="Name")]
    )
    if theme is not None:
        properties.theme = Theme(**theme)
    return StandardFormField(id="page-1", index=0, type=T.SLIDE, properties=properties)


def _form(theme=None, page_theme=None) -> StandardForm:
    return StandardForm(
        title="Form",
        builder_version="v2",
        theme=Theme(**theme) if theme else None,
        fields=[_page(page_theme)],
    )


def _body(theme=None, page_theme=None) -> dict:
    page = {"id": "page-1", "index": 0, "type": "slide", "properties": {"fields": []}}
    if page_theme is not None:
        page["properties"]["theme"] = page_theme
    return {"title": "Themed", "builder_version": "v2", "theme": theme, "fields": [page]}


async def _save(client, workspace, form, cookies, payload):
    return await client.patch(
        f"{API}/workspaces/{workspace.id}/forms/{form.form_id}",
        cookies=cookies,
        data={"form_body": json.dumps(payload)},
    )


@pytest.fixture
def off(monkeypatch):
    monkeypatch.setattr(settings.app_theme, "ENABLED", False)


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setattr(settings.app_theme, "ENABLED", True)


def test_the_key_follows_the_pigment_switch(monkeypatch):
    assert GATED_THEME_KEYS == {"choiceKeys": "app_theme.ENABLED"}
    monkeypatch.setattr(settings.app_theme, "ENABLED", False)
    assert not theme_key_offered("choiceKeys") and offered_theme_keys() == []
    monkeypatch.setattr(settings.app_theme, "ENABLED", True)
    assert theme_key_offered("choiceKeys") and offered_theme_keys() == ["choiceKeys"]


# --- a whole-form save ---------------------------------------------------------------


async def test_save_off_a_new_key_is_refused(client, workspace, workspace_form, test_user_cookies, off):
    response = await _save(client, workspace, workspace_form, test_user_cookies, _body(KEYED))
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "theme_not_allowed"
    assert response.json()["message"] == f"theme.{REFUSED}"
    stored = await container.form_service().get_form_document_by_id(workspace_form.form_id)
    assert stored.theme is None or stored.theme.choiceKeys is None


async def test_save_off_a_new_key_on_a_page_is_refused(
    client, workspace, workspace_form, test_user_cookies, off
):
    response = await _save(
        client, workspace, workspace_form, test_user_cookies, _body(PLAIN, page_theme=KEYED)
    )
    assert response.status_code == 422, response.text
    assert response.json()["message"] == f"fields.0.properties.theme.{REFUSED}"


async def test_save_off_a_theme_without_the_key_saves(
    client, workspace, workspace_form, test_user_cookies, off
):
    response = await _save(client, workspace, workspace_form, test_user_cookies, _body(PLAIN))
    assert response.status_code == 200, response.text


async def test_save_off_a_stored_key_still_saves(
    client, workspace, workspace_form, test_user_cookies, monkeypatch
):
    monkeypatch.setattr(settings.app_theme, "ENABLED", True)
    response = await _save(client, workspace, workspace_form, test_user_cookies, _body(KEYED))
    assert response.status_code == 200, response.text
    monkeypatch.setattr(settings.app_theme, "ENABLED", False)
    renamed = _body({**KEYED, "title": "Renamed"})
    response = await _save(client, workspace, workspace_form, test_user_cookies, renamed)
    assert response.status_code == 200, response.text
    stored = await container.form_service().get_form_document_by_id(workspace_form.form_id)
    assert stored.theme.choiceKeys == "letters"
    # ...and only at the place it is stored: the same key on a page is new
    response = await _save(
        client, workspace, workspace_form, test_user_cookies, _body(KEYED, page_theme=KEYED)
    )
    assert response.status_code == 422 and response.json()["message"].startswith("fields.0.")


async def test_save_on_a_new_key_saves(client, workspace, workspace_form, test_user_cookies, on):
    response = await _save(client, workspace, workspace_form, test_user_cookies, _body(KEYED))
    assert response.status_code == 200, response.text


# --- a new form ----------------------------------------------------------------------------


async def test_create_off_a_new_key_is_refused_and_a_copy_keeps_it(workspace, off):
    service = container.workspace_form_service()
    with pytest.raises(HTTPException) as error:
        await service.create_form(workspace.id, _form(KEYED), testUser)
    assert error.value.status_code == 422
    assert error.value.content["code"] == "theme_not_allowed"
    assert error.value.content["message"] == f"theme.{REFUSED}"
    # a copy of a form (or a template) keeps what its source has
    copy = await service.create_form(
        workspace.id, _form(KEYED), testUser, drop_unusable_settings=True, keep_theme=True
    )
    stored = await container.form_service().get_form_document_by_id(copy.form_id)
    assert stored.theme.choiceKeys == "letters"


async def test_create_on_a_new_key_saves(workspace, on):
    created = await container.workspace_form_service().create_form(
        workspace.id, _form(KEYED), testUser
    )
    assert created.form_id


# --- the edit operations -----------------------------------------------------------------------


def _ops(form, ops):
    return apply_form_ops(form, parse_ops(ops, allow_editor_ops=True), atomic=False)


def test_update_theme_off_a_new_key_is_refused(off):
    after, results = _ops(_form(PLAIN), [{"op": "update_theme", "theme": KEYED}])
    assert not results[0].ok
    assert results[0].message == f"theme.{REFUSED}"
    assert after.theme.choiceKeys is None


def test_update_theme_off_a_stored_key_is_kept(off):
    after, results = _ops(
        _form(KEYED), [{"op": "update_theme", "theme": {**KEYED, "title": "Renamed"}}]
    )
    assert results[0].ok, results[0].message
    assert after.theme.choiceKeys == "letters"


def test_update_theme_on_a_new_key_applies(on):
    after, results = _ops(_form(PLAIN), [{"op": "update_theme", "theme": KEYED}])
    assert results[0].ok and after.theme.choiceKeys == "letters"


def test_update_page_off_a_new_key_is_refused_and_a_stored_one_kept(off):
    patch = {"op": "update_page", "pageId": "page-1", "patch": {"theme": KEYED}}
    _, results = _ops(_form(PLAIN), [patch])
    assert not results[0].ok and results[0].message == f"theme.{REFUSED}"
    after, results = _ops(_form(PLAIN, page_theme=KEYED), [patch])
    assert results[0].ok, results[0].message
    assert after.fields[0].properties.theme.choiceKeys == "letters"


# --- the one write path of the op writers (AI, MCP, the public API) -------------------------------------


async def test_persist_form_off_a_new_key_is_refused_and_a_stored_one_kept(workspace, monkeypatch):
    monkeypatch.setattr(settings.app_theme, "ENABLED", True)
    created = await container.workspace_form_service().create_form(
        workspace.id, _form(KEYED), testUser
    )
    repo = container.form_repo()
    document = await repo.get_form_document_by_id(str(created.form_id))
    monkeypatch.setattr(settings.app_theme, "ENABLED", False)
    # what the form already wears
    assert await persist_form(repo, document, _form({**KEYED, "title": "Renamed"}), parts=["theme"])
    # a page's own theme is new
    with pytest.raises(HTTPException) as error:
        await persist_form(repo, document, _form(KEYED, page_theme=KEYED), parts=["theme", "fields"])
    assert error.value.content["code"] == "theme_not_allowed"
    assert error.value.content["message"] == f"fields.0.properties.theme.{REFUSED}"


# --- a workspace's saved themes ---------------------------------------------------------------------------


async def test_saved_themes_off_a_new_key_is_refused_and_a_stored_one_kept(
    client, workspace, test_user_cookies, monkeypatch
):
    url = f"{API}/workspaces/{workspace.id}/theme-presets"
    monkeypatch.setattr(settings.app_theme, "ENABLED", False)
    response = await client.patch(url, cookies=test_user_cookies, json=[KEYED])
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "theme_not_allowed"
    assert response.json()["message"] == f"customThemes.0.{REFUSED}"
    monkeypatch.setattr(settings.app_theme, "ENABLED", True)
    response = await client.patch(url, cookies=test_user_cookies, json=[KEYED])
    assert response.status_code == 200, response.text
    monkeypatch.setattr(settings.app_theme, "ENABLED", False)
    # the stored theme stays (here after another theme joined and moved it)
    other = {**PLAIN, "title": "Other"}
    response = await client.patch(url, cookies=test_user_cookies, json=[other, KEYED])
    assert response.status_code == 200, response.text
    # a different title with the key is new
    response = await client.patch(
        url, cookies=test_user_cookies, json=[other, KEYED, {**KEYED, "title": "Dawn"}]
    )
    assert response.status_code == 422
    assert response.json()["message"] == f"customThemes.2.{REFUSED}"


# --- what the AI is told ---------------------------------------------------------------------------------


@pytest.mark.parametrize("switch", [False, True])
def test_the_ai_guide_never_names_the_key(monkeypatch, switch):
    monkeypatch.setattr(settings.app_theme, "ENABLED", switch)
    assert "choiceKeys" not in ops_guide()
    assert "choiceKeys" not in outline_system_prompt()


def test_the_mcp_tool_text_never_names_the_key():
    source = Path(__file__).resolve().parents[3] / "backend" / "app" / "mcp" / "server.py"
    assert "choiceKeys" not in source.read_text()


def test_gated_theme_keys_match_the_webapp():
    source = Path(__file__).resolve().parents[4] / "webapp" / "src" / "constants" / "theme.ts"
    if not source.exists():
        return
    block = re.search(
        r"export const GATED_THEME_KEYS: Readonly<Record<string, string>> = \{(.*?)\};",
        source.read_text(),
        re.S,
    ).group(1)
    assert dict(re.findall(r"(\w+): '([\w.]+)'", block)) == GATED_THEME_KEYS
