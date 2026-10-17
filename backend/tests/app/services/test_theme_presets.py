"""The backend's theme presets (used for AI-created forms) match the webapp."""

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.constants.themes import (
    NEW_FORM_THEME,
    THEME_STYLES,
    get_themes_for_ai,
    themes,
)
from backend.app.models.workspace import WorkspaceThemeDto

WEBAPP_THEME_TS = (
    Path(__file__).resolve().parents[4] / "webapp" / "src" / "constants" / "theme.ts"
)


def test_default_preset_uses_the_sireto_values():
    default = themes["Default"]
    assert (default.primary, default.secondary, default.tertiary, default.accent) == (
        "#101828",
        "#1649E2",
        "#818CA0",
        "#F5F7FB",
    )


def test_default_preset_matches_the_webapp_preset():
    if not WEBAPP_THEME_TS.exists():  # backend checked out on its own
        return
    source = WEBAPP_THEME_TS.read_text()
    block = re.search(r"title: 'Default',(.*?)}", source, re.S).group(1)
    webapp = dict(re.findall(r"(\w+): '(#[0-9A-Fa-f]{6})'", block))
    default = themes["Default"]
    assert webapp == {
        "primary": default.primary,
        "secondary": default.secondary,
        "tertiary": default.tertiary,
        "accent": default.accent,
    }


def test_ai_theme_list_carries_the_default_colours():
    by_name = {entry["name"]: entry for entry in get_themes_for_ai()}
    assert by_name["Default"]["colors"]["secondary"] == "#1649E2"


def test_theme_styles_match_the_webapp():
    if not WEBAPP_THEME_TS.exists():  # backend checked out on its own
        return
    source = WEBAPP_THEME_TS.read_text()
    block = re.search(
        r"THEME_STYLES: ReadonlyArray<ThemeStyle> = \[(.*?)\]", source, re.S
    ).group(1)
    assert tuple(re.findall(r"'(\w+)'", block)) == THEME_STYLES


LEAFLET = {
    "title": "Leaflet",
    "primary": "#1A1A1A",
    "secondary": "#0B3D91",
    "tertiary": "#6B7A99",
    "accent": "#FFFFFF",
}


@pytest.mark.parametrize("style", THEME_STYLES)
def test_saved_themes_accept_every_style(style):
    assert WorkspaceThemeDto(**LEAFLET, style=style).style == style


def test_saved_themes_refuse_an_unknown_style():
    with pytest.raises(ValidationError):
        WorkspaceThemeDto(**LEAFLET, style="risograph")


def test_leaflet_preset_matches_the_webapp_preset():
    leaflet = themes["Leaflet"]
    assert {**LEAFLET, "style": "leaflet"} == {
        "title": leaflet.title,
        "primary": leaflet.primary,
        "secondary": leaflet.secondary,
        "tertiary": leaflet.tertiary,
        "accent": leaflet.accent,
        "style": leaflet.style,
    }
    if not WEBAPP_THEME_TS.exists():  # backend checked out on its own
        return
    source = WEBAPP_THEME_TS.read_text()
    block = re.search(r"title: 'Leaflet',(.*?)}", source, re.S).group(1)
    webapp = dict(re.findall(r"(\w+): '(#[0-9A-Fa-f]{6}|\w+)'", block))
    assert webapp == {
        "primary": leaflet.primary,
        "secondary": leaflet.secondary,
        "tertiary": leaflet.tertiary,
        "accent": leaflet.accent,
        "style": leaflet.style,
    }


def test_new_forms_start_with_the_same_preset_as_the_webapp():
    assert themes[NEW_FORM_THEME].style == "leaflet"
    if not WEBAPP_THEME_TS.exists():  # backend checked out on its own
        return
    source = WEBAPP_THEME_TS.read_text()
    webapp = re.search(r"NEW_FORM_THEME_TITLE = '(\w+)'", source).group(1)
    assert webapp == NEW_FORM_THEME
