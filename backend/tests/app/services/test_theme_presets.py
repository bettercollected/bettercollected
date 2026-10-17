"""The backend's theme presets (used for AI-created forms) match the webapp."""

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.constants.themes import (
    NEW_FORM_THEME,
    THEME_STYLES,
    get_themes_for_ai,
    preset_name,
    theme_descriptions,
    theme_dict,
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


def _webapp_presets() -> list[dict]:
    """The webapp's ThemeColors, read from theme.ts: one dict per preset, in
    the picker's order."""
    source = WEBAPP_THEME_TS.read_text()
    block = re.search(
        r"export const ThemeColors: Array<FormTheme> = \[(.*?)\n\];", source, re.S
    ).group(1)
    return [
        dict(re.findall(r"(\w+): '([^']*)'", entry))
        for entry in re.findall(r"\{(.*?)\}", block, re.S)
    ]


def test_every_preset_matches_the_webapp_list():
    """The webapp's list is the source of truth: same names, same order, same
    colours and style, so a preset the AI picks shows as that preset in the
    builder's picker (which matches by title)."""
    if not WEBAPP_THEME_TS.exists():  # backend checked out on its own
        return
    webapp = _webapp_presets()
    assert len(webapp) >= 10, "theme.ts no longer parses; update _webapp_presets"
    assert webapp == list(theme_dict.values())


def test_every_preset_has_a_description_for_the_ai():
    assert set(theme_descriptions) == set(theme_dict)
    assert all(entry["description"] for entry in get_themes_for_ai())


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Ocean", "Ocean"),
        ("  ocean ", "Ocean"),
        ("LEAFLET", "Leaflet"),
        ("Blue", "Ocean"),
        ("green", "Forest"),
        ("Red", "Cherry"),
        ("black", "Mono"),
        ("Orange", "Sunset"),
        ("purple", "Lavender"),
        ("Neon", None),
        ("", None),
        (None, None),
        (3, None),
    ],
)
def test_preset_name_resolves_current_and_legacy_names(name, expected):
    assert preset_name(name) == expected


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
