"""The chat can change a form's look: ``set_theme_preset`` by name (checked
against the presets), described in the guide, applied end to end through a
chat turn (a fake provider, never a real model)."""

import json
from typing import Any, Coroutine

import pytest
from httpx import AsyncClient

from common.models.standard_form import StandardForm, Theme, ThemeBackground

from backend.app.constants.themes import (
    NEW_FORM_THEME,
    THEME_STYLES,
    new_form_theme,
    theme_dict,
    themes,
)
from backend.app.container import container
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.services.ai.ops import apply_form_ops, parse_ops
from backend.app.services.ai.prompt_builder import OPS_GUIDE, project_form
from tests.app.ai_helpers import FakeProvider, enable_ai, use_fake_provider
from tests.app.controllers.test_form_ai_chat import _make_v2


def _form(theme=None) -> StandardForm:
    return StandardForm(form_id="f", title="T", fields=[], theme=theme)


def _apply(form, *ops):
    return apply_form_ops(form, parse_ops(list(ops)))


class TestTheOp:
    def test_a_preset_by_name_in_any_case(self):
        new_form, results = _apply(_form(new_form_theme()), {"op": "set_theme_preset", "name": " green "})
        assert results[0].ok, results[0].message
        expected = themes["Green"].model_dump(exclude={"style"})
        assert new_form.theme.model_dump(exclude={"style"}) == expected
        # a preset without a style of its own keeps the form's
        assert new_form.theme.style == "leaflet"

    def test_a_style_can_be_set_with_it(self):
        new_form, results = _apply(
            _form(new_form_theme()),
            {"op": "set_theme_preset", "name": "Default", "style": "Classic"},
        )
        assert results[0].ok, results[0].message
        assert new_form.theme.title == "Default"
        assert new_form.theme.style == "classic"

    def test_leaflet_brings_its_own_style_and_drops_a_background(self):
        old = themes["Blue"].model_copy(deep=True)
        old.style = "studio"
        old.background = ThemeBackground(type="pattern", pattern="dots")
        new_form, results = _apply(_form(old), {"op": "set_theme_preset", "name": "leaflet"})
        assert results[0].ok
        assert new_form.theme == themes[NEW_FORM_THEME]

    @pytest.mark.parametrize(
        "op",
        [
            {"op": "set_theme_preset", "name": "Neon"},
            {"op": "set_theme_preset", "name": "Green", "style": "brutalist"},
        ],
    )
    def test_an_unknown_name_or_style_fails_alone(self, op):
        before = new_form_theme()
        new_form, results = _apply(
            _form(before), op, {"op": "update_form_info", "title": "Still applied"}
        )
        assert not results[0].ok
        assert "Pick one of" in results[0].message
        assert results[1].ok
        assert new_form.theme == before
        assert new_form.title == "Still applied"

    def test_the_snapshot_names_the_current_look_without_colours(self):
        snapshot = json.loads(project_form(_form(new_form_theme())))
        assert snapshot["theme"] == {"name": "Leaflet", "style": "leaflet"}
        assert "#" not in json.dumps(snapshot["theme"])


class TestTheGuide:
    def test_it_lists_the_op_every_preset_and_style(self):
        assert '"op":"set_theme_preset"' in OPS_GUIDE
        assert '"op":"update_theme"' in OPS_GUIDE
        looks = OPS_GUIDE[OPS_GUIDE.index("## Looks"):]
        for name in theme_dict:
            assert f'- "{name}": ' in looks, name
        for style in THEME_STYLES:
            assert f'- "{style}": ' in looks, style
        assert f"New forms use the {NEW_FORM_THEME} preset" in looks
        assert "plainer" in looks

    def test_the_mcp_tool_names_every_preset(self):
        from backend.app.mcp import server

        doc = server.update_form.__doc__ or ""
        if not doc and hasattr(server.update_form, "fn"):
            doc = server.update_form.fn.__doc__
        assert '"op":"set_theme_preset"' in doc
        for name in theme_dict:
            assert name in doc, name


@pytest.fixture()
async def fake_provider(monkeypatch, workspace):
    fake = FakeProvider()
    use_fake_provider(monkeypatch, fake)
    await enable_ai(workspace)
    return fake


async def test_a_chat_turn_applies_a_theme_preset(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies: dict[str, str],
    fake_provider: FakeProvider,
):
    doc = await container.form_repo().get_form_document_by_id(workspace_form.form_id)
    await _make_v2(doc)
    fake_provider.replies = [
        json.dumps(
            {
                "reply": "The form now has a plainer look.",
                "ops": [{"op": "set_theme_preset", "name": "Default", "style": "classic"}],
            }
        )
    ]
    response = await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ai/chat",
        cookies=test_user_cookies,
        json={"message": "Use a plainer look"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [r["ok"] for r in body["results"]] == [True], body["results"]
    assert body["form"]["theme"]["title"] == "Default"
    assert "set_theme_preset" in fake_provider.calls[0]["system"]

    saved = await container.form_repo().get_form_document_by_id(workspace_form.form_id)
    assert saved.theme.title == "Default"
    assert saved.theme.style == "classic"
    assert saved.theme.secondary == theme_dict["Default"]["secondary"]


async def test_a_chat_turn_with_update_theme_still_applies(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies: dict[str, str],
    fake_provider: FakeProvider,
):
    doc = await container.form_repo().get_form_document_by_id(workspace_form.form_id)
    await _make_v2(doc)
    theme = Theme(
        title="Brand", primary="#111111", secondary="#0B3D91", tertiary="#6B7A99", accent="#FFFFFF"
    )
    fake_provider.replies = [
        json.dumps({"reply": "Done.", "ops": [{"op": "update_theme", "theme": theme.model_dump()}]})
    ]
    response = await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ai/chat",
        cookies=test_user_cookies,
        json={"message": "Use our colours: #111111 text, #0B3D91 buttons"},
    )
    assert response.status_code == 200, response.text
    assert [r["ok"] for r in response.json()["results"]] == [True]
    saved = await container.form_repo().get_form_document_by_id(workspace_form.form_id)
    assert saved.theme.title == "Brand"
