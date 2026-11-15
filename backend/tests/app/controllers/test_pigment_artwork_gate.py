"""The Pigment artwork is gated by APP_THEME_PIGMENT_ENABLED on every path that
takes an inline theme, not only by name.

While the switch is off, a theme that names ``background.artwork: "pigment"``
is refused as an unlisted artwork is, wherever it comes from: a whole-form save,
a new form, the edit operations, the one write path of the op writers (AI, MCP,
public API) and a workspace's saved themes. A theme the stored value already has
(the same path of the form, the same title among the saved themes) still saves,
so a form that wears it keeps working after the switch is turned off. A copy of a
form keeps what its source has."""

import json

import pytest
from common.models.standard_form import (
    StandardFieldProperty,
    StandardForm,
    StandardFormField,
    StandardFormFieldType as T,
    Theme,
)

from backend.app.constants.themes import theme_dict
from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.services.ai.ops import apply_form_ops, parse_ops
from backend.app.services.form_writes import persist_form
from backend.config import settings
from tests.app.controllers.data import testUser

API = "/api/v1"
PIGMENT = dict(theme_dict["Pigment"])
PLAIN = {k: PIGMENT[k] for k in ("title", "primary", "secondary", "tertiary", "accent")}
REFUSED = "background.artwork must be one of: marble."


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


# --- a whole-form save ---------------------------------------------------------------


async def test_save_off_a_new_artwork_is_refused(
    client, workspace, workspace_form, test_user_cookies, off
):
    response = await _save(client, workspace, workspace_form, test_user_cookies, _body(PIGMENT))
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "theme_not_allowed"
    assert response.json()["message"] == f"theme.{REFUSED}"
    stored = await container.form_service().get_form_document_by_id(workspace_form.form_id)
    assert stored.theme is None or (stored.theme.background or None) is None


async def test_save_off_a_new_artwork_on_a_page_is_refused(
    client, workspace, workspace_form, test_user_cookies, off
):
    response = await _save(
        client, workspace, workspace_form, test_user_cookies, _body(PLAIN, page_theme=PIGMENT)
    )
    assert response.status_code == 422, response.text
    assert response.json()["message"] == f"fields.0.properties.theme.{REFUSED}"


async def test_save_off_a_stored_artwork_still_saves(
    client, workspace, workspace_form, test_user_cookies, monkeypatch
):
    monkeypatch.setattr(settings.app_theme, "ENABLED", True)
    response = await _save(client, workspace, workspace_form, test_user_cookies, _body(PIGMENT))
    assert response.status_code == 200, response.text
    monkeypatch.setattr(settings.app_theme, "ENABLED", False)
    renamed = _body({**PIGMENT, "title": "Mine"})
    response = await _save(client, workspace, workspace_form, test_user_cookies, renamed)
    assert response.status_code == 200, response.text
    stored = await container.form_service().get_form_document_by_id(workspace_form.form_id)
    assert stored.theme.background.artwork == "pigment"
    # ...and only at the place it is stored: the same artwork on a page is new
    response = await _save(
        client, workspace, workspace_form, test_user_cookies, _body(PIGMENT, page_theme=PIGMENT)
    )
    assert response.status_code == 422 and response.json()["message"].startswith("fields.0.")


async def test_save_on_a_new_artwork_saves(
    client, workspace, workspace_form, test_user_cookies, on
):
    response = await _save(client, workspace, workspace_form, test_user_cookies, _body(PIGMENT))
    assert response.status_code == 200, response.text


# --- a new form ----------------------------------------------------------------------------


async def test_create_off_a_new_artwork_is_refused_and_a_copy_keeps_it(workspace, off):
    service = container.workspace_form_service()
    with pytest.raises(HTTPException) as error:
        await service.create_form(workspace.id, _form(PIGMENT), testUser)
    assert error.value.status_code == 422
    assert error.value.content["code"] == "theme_not_allowed"
    assert error.value.content["message"] == f"theme.{REFUSED}"
    # a copy of a form (or a template) keeps what its source has
    copy = await service.create_form(
        workspace.id, _form(PIGMENT), testUser, drop_unusable_settings=True, keep_theme=True
    )
    stored = await container.form_service().get_form_document_by_id(copy.form_id)
    assert stored.theme.background.artwork == "pigment"


async def test_create_on_a_new_artwork_saves(workspace, on):
    created = await container.workspace_form_service().create_form(
        workspace.id, _form(PIGMENT), testUser
    )
    assert created.form_id


# --- the edit operations -----------------------------------------------------------------------


def _ops(form, ops):
    return apply_form_ops(form, parse_ops(ops, allow_editor_ops=True), atomic=False)


def test_update_theme_off_a_new_artwork_is_refused(off):
    after, results = _ops(_form(PLAIN), [{"op": "update_theme", "theme": PIGMENT}])
    assert not results[0].ok
    assert results[0].message == f"theme.{REFUSED}"
    assert after.theme.background is None


def test_update_theme_off_a_stored_artwork_is_kept(off):
    after, results = _ops(_form(PIGMENT), [{"op": "update_theme", "theme": {**PIGMENT, "title": "Mine"}}])
    assert results[0].ok, results[0].message
    assert after.theme.background.artwork == "pigment"


def test_update_theme_on_a_new_artwork_applies(on):
    after, results = _ops(_form(PLAIN), [{"op": "update_theme", "theme": PIGMENT}])
    assert results[0].ok and after.theme.background.artwork == "pigment"


def test_update_page_off_a_new_artwork_is_refused_and_a_stored_one_kept(off):
    patch = {"op": "update_page", "pageId": "page-1", "patch": {"theme": PIGMENT}}
    _, results = _ops(_form(PLAIN), [patch])
    assert not results[0].ok and results[0].message == f"theme.{REFUSED}"
    after, results = _ops(_form(PLAIN, page_theme=PIGMENT), [patch])
    assert results[0].ok, results[0].message
    assert after.fields[0].properties.theme.background.artwork == "pigment"


# --- the one write path of the op writers (AI, MCP, the public API) -------------------------------------


async def test_persist_form_off_a_new_artwork_is_refused_and_a_stored_one_kept(workspace, monkeypatch):
    monkeypatch.setattr(settings.app_theme, "ENABLED", True)
    created = await container.workspace_form_service().create_form(
        workspace.id, _form(PIGMENT), testUser
    )
    repo = container.form_repo()
    document = await repo.get_form_document_by_id(str(created.form_id))
    monkeypatch.setattr(settings.app_theme, "ENABLED", False)
    # what the form already wears
    assert await persist_form(repo, document, _form({**PIGMENT, "title": "Mine"}), parts=["theme"])
    # a page's own theme is new
    with pytest.raises(HTTPException) as error:
        await persist_form(repo, document, _form(PIGMENT, page_theme=PIGMENT), parts=["theme", "fields"])
    assert error.value.content["code"] == "theme_not_allowed"
    assert error.value.content["message"] == f"fields.0.properties.theme.{REFUSED}"


# --- a workspace's saved themes ---------------------------------------------------------------------------


async def test_saved_themes_off_a_new_artwork_is_refused_and_a_stored_one_kept(
    client, workspace, test_user_cookies, monkeypatch
):
    url = f"{API}/workspaces/{workspace.id}/theme-presets"
    monkeypatch.setattr(settings.app_theme, "ENABLED", False)
    response = await client.patch(url, cookies=test_user_cookies, json=[PIGMENT])
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "theme_not_allowed"
    assert response.json()["message"] == f"customThemes.0.{REFUSED}"
    monkeypatch.setattr(settings.app_theme, "ENABLED", True)
    response = await client.patch(url, cookies=test_user_cookies, json=[PIGMENT])
    assert response.status_code == 200, response.text
    monkeypatch.setattr(settings.app_theme, "ENABLED", False)
    # the stored theme stays (here after another theme joined and moved it)
    other = {**PLAIN, "title": "Other"}
    response = await client.patch(url, cookies=test_user_cookies, json=[other, PIGMENT])
    assert response.status_code == 200, response.text
    # a different title with the artwork is new
    response = await client.patch(
        url, cookies=test_user_cookies, json=[other, PIGMENT, {**PIGMENT, "title": "Dawn"}]
    )
    assert response.status_code == 422
    assert response.json()["message"] == f"customThemes.2.{REFUSED}"
