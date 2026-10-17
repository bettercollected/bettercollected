"""What a new form starts with, and a page's own section title.

New forms that bring no theme of their own start with the Leaflet preset
(constants/themes.py NEW_FORM_THEME), whichever way they are made; a form
made from a template and a copy keep their source's theme.

A question page may carry a section title (properties.section_title): it is
stored with the form, goes live with a publish, is copied with the form, and
an older client that leaves it out keeps the stored one."""

import json

import pytest
from httpx import AsyncClient

from common.models.standard_form import StandardForm, Theme

from backend.app.constants.themes import NEW_FORM_THEME, new_form_theme, themes
from backend.app.container import container
from backend.app.schemas.template import FormTemplateDocument
from tests.app.controllers.data import formData, testUser

LEAFLET = {
    "title": "Leaflet",
    "primary": "#1A1A1A",
    "secondary": "#0B3D91",
    "tertiary": "#6B7A99",
    "accent": "#FFFFFF",
    "style": "leaflet",
}
OWN_THEME = {
    "title": "Mine",
    "primary": "#111827",
    "secondary": "#1D4ED8",
    "tertiary": "#2563EB",
    "accent": "#DBEAFE",
    "style": "sheet",
}


def _theme(value) -> dict:
    if value is None:
        return None
    if not isinstance(value, dict):
        value = value.model_dump()
    return {k: v for k, v in value.items() if k != "background" and v is not None}


def _forms_url(workspace, form_id=""):
    base = f"/api/v1/workspaces/{workspace.id}/forms"
    return f"{base}/{form_id}" if form_id else base


# -- new forms start with Leaflet ---------------------------------------------


def test_new_forms_start_with_the_leaflet_preset():
    assert NEW_FORM_THEME == "Leaflet"
    assert _theme(new_form_theme()) == LEAFLET
    # a fresh copy each time: changing one form's theme never touches another's
    new_form_theme().primary = "#000000"
    assert themes["Leaflet"].primary == "#1A1A1A"


async def test_a_blank_form_from_the_api_starts_with_leaflet(
    client: AsyncClient, workspace, test_user_cookies
):
    body = {k: v for k, v in formData.items() if k != "theme"}
    reply = await client.post(
        _forms_url(workspace),
        data={"form_body": json.dumps(body)},
        cookies=test_user_cookies,
    )
    assert reply.status_code == 200, reply.text
    assert _theme(reply.json()["theme"]) == LEAFLET
    stored = await container.form_repo().get_form_document_by_id(reply.json()["formId"])
    assert _theme(stored.theme) == LEAFLET


async def test_a_form_that_brings_its_theme_keeps_it(
    client: AsyncClient, workspace, test_user_cookies
):
    reply = await client.post(
        _forms_url(workspace),
        data={"form_body": json.dumps({**formData, "theme": OWN_THEME})},
        cookies=test_user_cookies,
    )
    assert reply.status_code == 200, reply.text
    assert _theme(reply.json()["theme"]) == OWN_THEME


# (a form made through MCP: tests/app/controllers/test_mcp_server.py)


@pytest.mark.parametrize(
    "picked, expected",
    [
        ({}, "Leaflet"),
        ({"theme_name": "Leaflet"}, "Leaflet"),
        ({"theme_name": "Forest"}, "Forest"),
        # a legacy preset name means the nearest preset
        ({"theme_name": "Green"}, "Forest"),
        ({"theme_name": "purple"}, "Lavender"),
        ({"theme_name": "Neon"}, "Leaflet"),
        ({"theme_name": None}, "Leaflet"),
    ],
)
def test_an_ai_created_form_starts_with_leaflet_unless_a_preset_was_picked(
    picked, expected
):
    form = container.openai_service().convert_openai_form_to_standard_form(
        {"title": "Intake", "fields": [], **picked}
    )
    assert form.theme.title == expected
    if expected == "Leaflet":
        assert _theme(form.theme) == LEAFLET


async def test_a_form_from_a_template_keeps_the_template_theme(
    client: AsyncClient, workspace, test_user_cookies
):
    themed = FormTemplateDocument(
        title="Themed", settings={"is_public": True}, theme=Theme(**OWN_THEME)
    )
    themed.workspace_id = workspace.id
    themed = await container.form_template_repo().save(themed)
    plain = FormTemplateDocument(title="Plain", settings={"is_public": True})
    plain.workspace_id = workspace.id
    plain = await container.form_template_repo().save(plain)

    reply = await client.post(
        f"/api/v1/workspaces/{workspace.id}/template/{themed.id}",
        cookies=test_user_cookies,
    )
    assert reply.status_code == 200, reply.text
    assert _theme(reply.json()["theme"]) == OWN_THEME

    # a template made without a theme still renders as it always did
    reply = await client.post(
        f"/api/v1/workspaces/{workspace.id}/template/{plain.id}",
        cookies=test_user_cookies,
    )
    assert reply.status_code == 200, reply.text
    assert reply.json().get("theme") is None


async def test_a_copy_keeps_the_source_theme(
    client: AsyncClient, workspace, test_user_cookies
):
    source = await container.workspace_form_service().create_form(
        workspace.id, StandardForm(**{**formData, "theme": OWN_THEME}), testUser
    )
    reply = await client.post(
        f"{_forms_url(workspace, source.form_id)}/duplicate",
        cookies=test_user_cookies,
    )
    assert reply.status_code == 200, reply.text
    assert _theme(reply.json()["theme"]) == OWN_THEME


async def test_a_provider_import_starts_with_leaflet_and_a_reimport_keeps_the_theme():
    service = container.form_service()
    imported = StandardForm(form_id="provider-form-1", title="From Google")
    first = await service.save_form(imported)
    assert _theme(first.theme) == LEAFLET
    version = await container.form_repo().get_form_by_by_version("provider-form-1", 1)
    assert _theme(version.theme) == LEAFLET

    # the creator picks another theme; a re-import (no colours) keeps it
    first.theme = Theme(**OWN_THEME)
    await container.form_repo().save_form(first)
    again = await service.save_form(
        StandardForm(form_id="provider-form-1", title="From Google")
    )
    assert _theme(again.theme) == OWN_THEME

    # a provider that sends its own colours keeps them
    own = await service.save_form(
        StandardForm(form_id="provider-form-2", title="Typeform", theme=OWN_THEME)
    )
    assert _theme(own.theme) == OWN_THEME


# -- a page's own section title -------------------------------------------------


def _page(title=None, page_id="page-1", **extra):
    properties = {
        "layout": "SINGLE_COLUMN_NO_BACKGROUND",
        "fields": [
            {
                "id": f"{page_id}-q",
                "index": 0,
                "type": "short_text",
                "title": "Favourite colour",
                "properties": {},
            }
        ],
        **extra,
    }
    if title is not None:
        properties["sectionTitle"] = title
    return {"id": page_id, "index": 0, "type": "slide", "properties": properties}


def _body(*pages):
    return {
        "title": "Sections",
        "builderVersion": "v2",
        "fields": list(pages),
        "thankyouPage": [{"layout": "SINGLE_COLUMN_NO_BACKGROUND"}],
    }


async def _save(client, workspace, form_id, cookies, body):
    return await client.patch(
        _forms_url(workspace, form_id),
        data={"form_body": json.dumps(body)},
        cookies=cookies,
    )


def _titles(form_json):
    return [
        (page.get("properties") or {}).get("sectionTitle")
        for page in form_json["fields"]
    ]


async def test_a_section_title_round_trips_and_an_older_client_keeps_it(
    client: AsyncClient, workspace, workspace_form, test_user_cookies
):
    form_id = workspace_form.form_id
    reply = await _save(
        client,
        workspace,
        form_id,
        test_user_cookies,
        _body(_page("  About you  "), _page(page_id="page-2")),
    )
    assert reply.status_code == 200, reply.text
    assert _titles(reply.json()) == ["About you", None]

    # an older client sends the pages without the setting: the title stays
    reply = await _save(
        client,
        workspace,
        form_id,
        test_user_cookies,
        _body(_page(), _page(page_id="page-2")),
    )
    assert _titles(reply.json()) == ["About you", None]
    stored = await container.form_repo().get_form_document_by_id(form_id)
    assert stored.fields[0].properties.section_title == "About you"

    # an empty title clears it (the bar falls back to the page's heading or
    # its first question)
    reply = await _save(
        client, workspace, form_id, test_user_cookies, _body(_page("   "))
    )
    assert _titles(reply.json()) == [None]
    stored = await container.form_repo().get_form_document_by_id(form_id)
    assert stored.fields[0].properties.section_title is None


async def test_a_section_title_has_a_length_cap(
    client: AsyncClient, workspace, workspace_form, test_user_cookies
):
    reply = await _save(
        client,
        workspace,
        workspace_form.form_id,
        test_user_cookies,
        _body(_page("x" * 121)),
    )
    assert reply.status_code == 422
    reply = await _save(
        client,
        workspace,
        workspace_form.form_id,
        test_user_cookies,
        _body(_page("x" * 120)),
    )
    assert reply.status_code == 200, reply.text


async def test_a_section_title_goes_live_and_is_copied(
    client: AsyncClient, workspace, workspace_form, test_user_cookies
):
    form_id = workspace_form.form_id
    reply = await _save(
        client, workspace, form_id, test_user_cookies, _body(_page("Your visit"))
    )
    assert reply.status_code == 200, reply.text
    await container.workspace_form_service().publish_form(
        workspace.id, form_id, testUser
    )
    live = await client.get(_forms_url(workspace, form_id), params={"published": True})
    assert live.status_code == 200, live.text
    assert _titles(live.json()) == ["Your visit"]

    copy = await client.post(
        f"{_forms_url(workspace, form_id)}/duplicate", cookies=test_user_cookies
    )
    assert copy.status_code == 200, copy.text
    assert _titles(copy.json()) == ["Your visit"]


async def test_a_new_form_takes_its_section_titles_trimmed(
    client: AsyncClient, workspace, test_user_cookies
):
    reply = await client.post(
        _forms_url(workspace),
        data={
            "form_body": json.dumps(
                _body(_page(" Contact "), _page("", page_id="page-2"))
            )
        },
        cookies=test_user_cookies,
    )
    assert reply.status_code == 200, reply.text
    assert _titles(reply.json()) == ["Contact", None]
