"""The backend's theme presets (used for AI-created forms) match the webapp."""

import re
from pathlib import Path

import pytest
from common.form_spec.models import Theme as SpecTheme
from common.models.standard_form import (
    THEME_ARTWORKS,
    THEME_BUTTON_STYLES,
    THEME_FONTS,
    THEME_PATTERNS,
    THEME_RADII,
    THEME_TITLE_WIDTHS,
    THEME_TYPE_SHAPE_KEYS,
    theme_problems,
)
from pydantic import ValidationError

from backend.app.constants.themes import (
    NEW_FORM_THEME,
    PRESET_WELCOME_LAYOUTS,
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


def _top_level_objects(block: str) -> list[str]:
    """The bodies of the `{ ... }` objects at the top level of ``block``."""
    objects, depth, start = [], 0, 0
    for index, char in enumerate(block):
        if char == "{":
            if depth == 0:
                start = index + 1
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                objects.append(block[start:index])
    return objects


def _ts_object(body: str) -> dict:
    """A preset written as `key: 'value'` lines, with nested `key: { ... }`
    objects of the same."""
    nested = {}
    for match in re.finditer(r"(\w+): \{(.*?)\}", body, re.S):
        nested[match.group(1)] = _ts_object(match.group(2))
    flat = re.sub(r"(\w+): \{(.*?)\}", "", body, flags=re.S)
    return {**dict(re.findall(r"(\w+): '([^']*)'", flat)), **nested}


def _webapp_presets() -> list[dict]:
    """The webapp's ThemeColors, read from theme.ts: one dict per preset, in
    the picker's order."""
    source = WEBAPP_THEME_TS.read_text()
    block = re.search(
        r"export const ThemeColors: Array<FormTheme> = \[(.*?)\n\];", source, re.S
    ).group(1)
    return [_ts_object(entry) for entry in _top_level_objects(block)]


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


@pytest.mark.parametrize(
    "name, values",
    [
        ("THEME_FONTS", THEME_FONTS),
        ("THEME_TITLE_WIDTHS", THEME_TITLE_WIDTHS),
        ("THEME_RADII", THEME_RADII),
        ("THEME_BUTTON_STYLES", THEME_BUTTON_STYLES),
    ],
)
def test_type_and_shape_lists_match_the_webapp(name, values):
    if not WEBAPP_THEME_TS.exists():  # backend checked out on its own
        return
    source = WEBAPP_THEME_TS.read_text()
    block = re.search(
        rf"export const {name}: ReadonlyArray<\w+> = \[(.*?)\]", source, re.S
    ).group(1)
    assert tuple(re.findall(r"'([\w-]+)'", block)) == values


def test_the_spec_lists_the_same_values():
    schema = SpecTheme.model_json_schema(by_alias=True)["properties"]

    def listed(key):
        return tuple(schema[key]["anyOf"][0]["enum"])

    assert (
        listed("titleFont") == listed("bodyFont") == listed("dataFont") == THEME_FONTS
    )
    assert listed("titleWidth") == THEME_TITLE_WIDTHS
    assert listed("radius") == THEME_RADII
    assert listed("buttonStyle") == THEME_BUTTON_STYLES


COMPLETE_LOOKS = ("Kantlijn", "Raster")


def test_colour_presets_leave_type_and_shape_to_the_form():
    # The colour presets (and Leaflet's style) set no type or shape: picking
    # one keeps the form's own.
    for name, preset in themes.items():
        if name in COMPLETE_LOOKS:
            continue
        assert all(getattr(preset, key) is None for key in THEME_TYPE_SHAPE_KEYS)
        assert preset.highlight is None and preset.selection is None
        assert preset.background is None


@pytest.mark.parametrize("name", COMPLETE_LOOKS)
def test_complete_looks_set_every_type_and_shape_key(name):
    # Picking a preset keeps any type or shape key it leaves out, so a
    # complete look sets them all (normal width and filled buttons too),
    # and its style, so a form's earlier style never shows through.
    preset = themes[name]
    assert all(getattr(preset, key) is not None for key in THEME_TYPE_SHAPE_KEYS)
    assert preset.style in THEME_STYLES
    assert preset.background is not None and preset.background.type == "pattern"
    assert preset.background.pattern in THEME_PATTERNS


@pytest.mark.parametrize("name", list(theme_dict))
def test_every_preset_is_valid_in_every_writer(name):
    # The same checks the edit operations, whole-form saves and saved
    # workspace themes apply.
    assert theme_problems(theme_dict[name]) == []
    assert theme_problems(themes[name]) == []
    assert theme_problems(WorkspaceThemeDto(**theme_dict[name])) == []
    SpecTheme.model_validate(theme_dict[name])


def test_complete_looks_name_their_welcome_layout():
    assert PRESET_WELCOME_LAYOUTS == {
        "Kantlijn": "TWO_COLUMN_IMAGE_RIGHT",
        "Raster": "SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN",
    }
    if not WEBAPP_THEME_TS.exists():  # backend checked out on its own
        return
    source = WEBAPP_THEME_TS.read_text()
    block = re.search(
        r"PRESET_WELCOME_LAYOUTS: Readonly<Record<string, FormSlideLayout>> = \{(.*?)\}",
        source,
        re.S,
    ).group(1)
    assert dict(re.findall(r"(\w+): FormSlideLayout\.(\w+)", block)) == PRESET_WELCOME_LAYOUTS


@pytest.mark.parametrize(
    "name, values",
    [("THEME_PATTERNS", THEME_PATTERNS), ("THEME_ARTWORKS", THEME_ARTWORKS)],
)
def test_background_lists_match_the_webapp(name, values):
    if not WEBAPP_THEME_TS.exists():  # backend checked out on its own
        return
    source = WEBAPP_THEME_TS.read_text()
    block = re.search(
        rf"export const {name}: ReadonlyArray<\w+> = \[(.*?)\]", source, re.S
    ).group(1)
    assert tuple(re.findall(r"'([\w-]+)'", block)) == values


def test_saved_themes_take_the_new_patterns_and_artwork():
    for pattern in THEME_PATTERNS:
        saved = WorkspaceThemeDto(**LEAFLET, background={"type": "pattern", "pattern": pattern})
        assert saved.background.pattern == pattern
    saved = WorkspaceThemeDto(
        **LEAFLET, background={"type": "color", "artwork": "marble"}, selection="#1E4D3B"
    )
    assert (saved.background.artwork, saved.selection) == ("marble", "#1E4D3B")
    with pytest.raises(ValidationError):
        WorkspaceThemeDto(**LEAFLET, background={"type": "pattern", "pattern": "waves"})
    # An unlisted artwork or selection is refused by the endpoint's 422
    # (services/form_themes.py), like the other listed keys.
    assert theme_problems(
        WorkspaceThemeDto(
            **LEAFLET, background={"type": "color", "artwork": "photo"}, selection="green"
        ),
        "customThemes.0",
    ) == [
        "customThemes.0.selection must be a 6-digit hex colour, e.g. #1E4D3B.",
        "customThemes.0.background.artwork must be one of: marble.",
    ]


def test_theme_problems_names_the_selection_and_artwork():
    assert theme_problems(
        {**LEAFLET, "selection": "#1e4d3b", "background": {"artwork": "marble"}}
    ) == []
    assert theme_problems(
        {**LEAFLET, "selection": "cloth", "background": {"artwork": "paisley"}}
    ) == [
        "theme.selection must be a 6-digit hex colour, e.g. #1E4D3B.",
        "theme.background.artwork must be one of: marble.",
    ]
    # Stored patterns are not held to the list (older forms may carry others).
    assert theme_problems({**LEAFLET, "background": {"pattern": "waves"}}) == []


def test_theme_problems_names_every_unlisted_key():
    assert theme_problems(None) == []
    assert (
        theme_problems({**LEAFLET, "titleFont": "besley", "highlight": "#a3305a"}) == []
    )
    assert theme_problems(
        {
            "titleFont": "Besley",
            "bodyFont": "",
            "titleWidth": "125",
            "radius": "6px",
            "buttonStyle": "link",
            "highlight": "#A3305AFF",
        },
        "page.theme",
    ) == [
        "page.theme.titleFont must be one of: public-sans, atkinson-next, archivo, besley, rubik, atkinson-mono.",
        "page.theme.bodyFont must be one of: public-sans, atkinson-next, archivo, besley, rubik, atkinson-mono.",
        "page.theme.titleWidth must be one of: normal, expanded.",
        "page.theme.radius must be one of: sharp, soft, round.",
        "page.theme.buttonStyle must be one of: filled, outlined, pill.",
        "page.theme.highlight must be a 6-digit hex colour, e.g. #A3305A.",
    ]


def test_saved_themes_take_type_and_shape():
    saved = WorkspaceThemeDto(
        **LEAFLET,
        titleFont="archivo",
        titleWidth="expanded",
        radius="sharp",
        buttonStyle="outlined",
        highlight="#2B2FD1",
    )
    assert (saved.titleFont, saved.titleWidth, saved.radius) == (
        "archivo",
        "expanded",
        "sharp",
    )
    # Unlisted values are refused by the endpoint with the form save's 422
    # (services/form_themes.py), not by the model.
    assert theme_problems(
        WorkspaceThemeDto(**LEAFLET, bodyFont="helvetica", highlight="red"),
        "customThemes.0",
    ) == [
        "customThemes.0.bodyFont must be one of: public-sans, atkinson-next, archivo, besley, rubik, atkinson-mono.",
        "customThemes.0.highlight must be a 6-digit hex colour, e.g. #A3305A.",
    ]
