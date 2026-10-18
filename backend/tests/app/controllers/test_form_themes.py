"""A theme's type, shape and highlight keys (titleFont, bodyFont, dataFont,
titleWidth, radius, buttonStyle, highlight) on whole-form saves and saved
workspace themes: listed values are stored, anything else is refused before
anything is written (services/form_themes.py), and a theme without them is
stored as before."""

import json
from typing import Any, Coroutine

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument

API = "/api/v1"
COLOURS = {
    "title": "Mine",
    "primary": "#16261F",
    "secondary": "#1E4D3B",
    "tertiary": "#7D8C84",
    "accent": "#F8EEEC",
}
TYPE_SHAPE = {
    "titleFont": "besley",
    "bodyFont": "atkinson-next",
    "dataFont": "atkinson-mono",
    "titleWidth": "normal",
    "radius": "soft",
    "buttonStyle": "outlined",
    "highlight": "#A3305A",
}


def body(theme: dict, page_theme: dict | None = None) -> dict:
    page = {"id": "page-1", "index": 0, "type": "slide", "properties": {"fields": []}}
    if page_theme is not None:
        page["properties"]["theme"] = page_theme
    return {
        "title": "Themed",
        "builder_version": "v2",
        "theme": theme,
        "fields": [page],
    }


async def save(client, workspace, form, cookies, payload: dict):
    return await client.patch(
        f"{API}/workspaces/{workspace.id}/forms/{form.form_id}",
        cookies=cookies,
        data={"form_body": json.dumps(payload)},
    )


async def stored(form) -> FormDocument:
    return await container.form_service().get_form_document_by_id(form.form_id)


async def workspace_themes(workspace) -> list:
    saved = await container.workspace_repo().get_or_404(workspace.id)
    return [
        theme if isinstance(theme, dict) else theme.model_dump()
        for theme in saved.custom_themes or []
    ]


async def test_listed_type_and_shape_are_stored_and_returned(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies: dict[str, str],
):
    response = await save(
        client,
        workspace,
        workspace_form,
        test_user_cookies,
        body({**COLOURS, **TYPE_SHAPE}),
    )
    assert response.status_code == 200, response.text
    returned = response.json()["theme"]
    assert {key: returned[key] for key in TYPE_SHAPE} == TYPE_SHAPE
    theme = (await stored(workspace_form)).theme
    assert {key: getattr(theme, key) for key in TYPE_SHAPE} == TYPE_SHAPE


async def test_a_theme_without_them_is_stored_as_before(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies: dict[str, str],
):
    response = await save(
        client, workspace, workspace_form, test_user_cookies, body(COLOURS)
    )
    assert response.status_code == 200, response.text
    theme = (await stored(workspace_form)).theme
    assert theme.model_dump(exclude_none=True) == COLOURS


@pytest.mark.parametrize(
    "key, value",
    [
        ("titleFont", "comic-sans"),
        ("bodyFont", "Public Sans"),
        ("dataFont", "courier"),
        ("titleWidth", "wide"),
        ("radius", "pill"),
        ("buttonStyle", "ghost"),
        ("highlight", "rose"),
        ("highlight", "#A35"),
        ("highlight", "#A3305A; background: url(x)"),
    ],
)
async def test_an_unlisted_value_is_refused_and_nothing_is_written(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies: dict[str, str],
    key,
    value,
):
    before = (await stored(workspace_form)).theme
    response = await save(
        client,
        workspace,
        workspace_form,
        test_user_cookies,
        body({**COLOURS, key: value}),
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "theme_not_allowed"
    assert f"theme.{key}" in response.json()["message"]
    assert (await stored(workspace_form)).theme == before


async def test_a_page_theme_is_checked_too(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies: dict[str, str],
):
    response = await save(
        client,
        workspace,
        workspace_form,
        test_user_cookies,
        body(COLOURS, page_theme={**COLOURS, "radius": "huge"}),
    )
    assert response.status_code == 422, response.text
    assert "fields.0.properties.theme.radius" in response.json()["message"]


async def test_a_new_form_with_an_unlisted_font_is_refused(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    test_user_cookies: dict[str, str],
):
    response = await client.post(
        f"{API}/workspaces/{workspace.id}/forms",
        cookies=test_user_cookies,
        data={"form_body": json.dumps(body({**COLOURS, "titleFont": "papyrus"}))},
    )
    assert response.status_code == 422, response.text
    response = await client.post(
        f"{API}/workspaces/{workspace.id}/forms",
        cookies=test_user_cookies,
        data={"form_body": json.dumps(body({**COLOURS, "titleFont": "rubik"}))},
    )
    assert response.status_code == 200, response.text
    assert response.json()["theme"]["titleFont"] == "rubik"


async def test_saved_workspace_themes_keep_type_and_shape_and_refuse_others(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    test_user_cookies: dict[str, str],
):
    url = f"{API}/workspaces/{workspace.id}/theme-presets"
    response = await client.patch(
        url, cookies=test_user_cookies, json=[{**COLOURS, **TYPE_SHAPE}]
    )
    assert response.status_code == 200, response.text
    saved = response.json()["customThemes"][0]
    assert {key: saved[key] for key in TYPE_SHAPE} == TYPE_SHAPE
    response = await client.patch(
        url,
        cookies=test_user_cookies,
        json=[{**COLOURS, "title": "Other"}, {**COLOURS, "buttonStyle": "ghost"}],
    )
    # the same 422 body as a form save
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "theme_not_allowed"
    assert response.json()["message"] == (
        "customThemes.1.buttonStyle must be one of: filled, outlined, pill."
    )
    assert [t["title"] for t in (await workspace_themes(workspace))] == ["Mine"]
