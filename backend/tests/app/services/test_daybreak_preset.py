"""The Daybreak theme preset and its switch (``DAYBREAK_PRESET_ENABLED``).

On: the preset is offered to the builder's picker, the edit operations, the AI
and the MCP server. Off (the default): none of them knows it; the name is
refused as an unknown preset is, and nothing else changes. A form that stores
the theme keeps rendering, publishing and saving, whatever the switch says.
"""

import re
from pathlib import Path

import pytest
from common.models.standard_form import (
    THEME_ARTWORKS,
    StandardForm,
    StandardFormField,
    StandardFormFieldType as T,
    StandardFieldProperty,
    Theme,
    theme_problems,
)

from backend.app.constants.themes import (
    GATED_PRESETS,
    PICTURE_ARTWORKS,
    PRESET_WELCOME_LAYOUTS,
    get_themes_for_ai,
    offered_presets,
    preset_name,
    preset_offered,
    theme_dict,
    themes,
)
from backend.app.services.ai.ops import apply_form_ops, parse_ops
from backend.app.services.ai.prompt_builder import _looks_guide
from backend.app.services.publish_checks import theme_contrast_problems
from backend.app.services.theme_contrast import (
    AA_NON_TEXT,
    AA_TEXT,
    contrast,
    muted_label_ink,
    theme_contrast_guard,
)
from backend.config import settings

WEBAPP_THEME_TS = (
    Path(__file__).resolve().parents[4] / "webapp" / "src" / "constants" / "theme.ts"
)

DAYBREAK = theme_dict["Daybreak"]


@pytest.fixture
def switch_on(monkeypatch):
    monkeypatch.setattr(settings, "DAYBREAK_PRESET_ENABLED", True)


@pytest.fixture
def switch_off(monkeypatch):
    monkeypatch.setattr(settings, "DAYBREAK_PRESET_ENABLED", False)


def _form(theme=None) -> StandardForm:
    return StandardForm(
        title="Form",
        theme=Theme(**theme) if isinstance(theme, dict) else theme,
        fields=[
            StandardFormField(
                id="page-1",
                type=T.SLIDE,
                properties=StandardFieldProperty(
                    fields=[
                        StandardFormField(
                            id="q1", index=0, type=T.SHORT_TEXT, title="Your name"
                        )
                    ]
                ),
            )
        ],
    )


def _apply(form, *ops):
    return apply_form_ops(form, parse_ops(list(ops)), atomic=False)


# --- the switch is off by default ---------------------------------------------------


def test_the_switch_is_off_by_default():
    assert type(settings).model_fields["DAYBREAK_PRESET_ENABLED"].default is False


def test_the_preset_is_not_the_default_for_new_forms():
    from backend.app.constants.themes import NEW_FORM_THEME

    assert NEW_FORM_THEME == "Leaflet"


# --- off: an unknown preset in every reader ----------------------------------------


@pytest.mark.parametrize("name", ["Daybreak", "daybreak", "  DAYBREAK "])
def test_off_the_name_means_no_preset(switch_off, name):
    assert preset_name(name) is None


def test_off_it_is_not_offered_or_listed(switch_off):
    assert not preset_offered("Daybreak")
    assert "Daybreak" not in offered_presets()
    assert "Daybreak" not in [entry["name"] for entry in get_themes_for_ai()]
    assert "Daybreak" not in _looks_guide()
    # the others stay
    assert offered_presets() == [n for n in theme_dict if n != "Daybreak"]


def test_off_set_theme_preset_refuses_it_as_it_refuses_an_unknown_name(switch_off):
    _, unknown = _apply(_form(), {"op": "set_theme_preset", "name": "Neon"})
    _, refused = _apply(_form(), {"op": "set_theme_preset", "name": "Daybreak"})
    assert not refused[0].ok
    assert refused[0].message == unknown[0].message.replace("Neon", "Daybreak")
    assert "Daybreak" not in refused[0].message.split("Pick one of:")[1]


def test_off_the_form_is_not_changed(switch_off):
    form = _form()
    after, results = _apply(form, {"op": "set_theme_preset", "name": "Daybreak"})
    assert not results[0].ok
    assert after.theme == form.theme


def test_off_the_other_presets_still_work(switch_off):
    after, results = _apply(_form(), {"op": "set_theme_preset", "name": "Ocean"})
    assert results[0].ok and after.theme.title == "Ocean"


def test_off_a_form_that_stores_the_theme_still_edits_and_saves(switch_off):
    form = _form(DAYBREAK)
    after, results = _apply(
        form,
        {"op": "update_field", "fieldId": "q1", "patch": {"title": "Full name"}},
    )
    assert results[0].ok, results[0].message
    assert after.theme.title == "Daybreak"
    assert after.theme.background.artwork == "daybreak"
    # the stored values are valid in every writer and publish
    assert theme_problems(after.theme) == []
    assert theme_contrast_problems(after.theme) == []


# --- on: offered everywhere -----------------------------------------------------------


def test_on_it_is_offered(switch_on):
    assert preset_name("daybreak") == "Daybreak"
    assert "Daybreak" in offered_presets()
    assert "Daybreak" in [entry["name"] for entry in get_themes_for_ai()]
    assert '"Daybreak"' in _looks_guide()


def test_on_set_theme_preset_applies_it_and_keeps_the_forms_faces(switch_on):
    form = _form(
        {
            "title": "Looks",
            "primary": "#16261F",
            "secondary": "#1E4D3B",
            "tertiary": "#7D8C84",
            "accent": "#F8EEEC",
            "titleFont": "besley",
            "radius": "soft",
            "highlight": "#A3305A",
        }
    )
    after, results = _apply(form, {"op": "set_theme_preset", "name": "daybreak"})
    assert results[0].ok, results[0].message
    theme = after.theme
    assert (theme.title, theme.accent, theme.secondary) == ("Daybreak", "#F3F6FF", "#1649E2")
    assert theme.style == "classic"
    assert theme.background.artwork == "daybreak"
    # a scene preset, not a complete look: faces and corners stay, the old highlight goes
    assert (theme.titleFont, theme.radius) == ("besley", "soft")
    assert theme.highlight is None


def test_it_does_not_change_the_welcome_layout_by_itself(switch_on):
    assert "Daybreak" not in PRESET_WELCOME_LAYOUTS
    assert "daybreak" not in PICTURE_ARTWORKS


# --- the list of gated presets -------------------------------------------------------


def test_the_gated_presets_name_a_real_setting_and_a_real_preset():
    for name, switch in GATED_PRESETS.items():
        assert name in theme_dict
        assert switch in type(settings).model_fields


def test_the_gated_presets_match_the_webapp():
    if not WEBAPP_THEME_TS.exists():  # backend checked out on its own
        return
    source = WEBAPP_THEME_TS.read_text()
    block = re.search(
        r"export const GATED_PRESETS: ReadonlyArray<string> = \[(.*?)\]", source, re.S
    ).group(1)
    assert tuple(re.findall(r"'(\w+)'", block)) == tuple(GATED_PRESETS)


def test_the_picture_artworks_match_the_webapp():
    if not WEBAPP_THEME_TS.exists():
        return
    source = WEBAPP_THEME_TS.read_text()
    block = re.search(
        r"export const PICTURE_ARTWORKS: ReadonlyArray<ThemeArtwork> = \[(.*?)\]",
        source,
        re.S,
    ).group(1)
    assert tuple(re.findall(r"'(\w+)'", block)) == PICTURE_ARTWORKS


def test_daybreak_artwork_is_on_the_list():
    assert "daybreak" in THEME_ARTWORKS


# --- contrast ------------------------------------------------------------------------

# The pairs the form draws, in light values (the webapp's theme-pins and
# daybreak tests read the same numbers): role, foreground, background, minimum.
PAGE = DAYBREAK["accent"]
PAIRS = [
    ("questions and text on the page", DAYBREAK["primary"], PAGE, AA_TEXT),
    ("answers typed in the white input boxes", DAYBREAK["primary"], "#FFFFFF", AA_TEXT),
    ("button text on the action colour", "#FFFFFF", DAYBREAK["secondary"], AA_TEXT),
    ("action colour (chosen answer, progress, focus ring) on the page", DAYBREAK["secondary"], PAGE, AA_NON_TEXT),
    ("input borders on the page", DAYBREAK["tertiary"], PAGE, AA_NON_TEXT),
    ("input borders on the white input boxes", DAYBREAK["tertiary"], "#FFFFFF", AA_NON_TEXT),
    ("the 'why we ask' rule on the page", "#B07400", PAGE, AA_NON_TEXT),
    ("ink on the sun in the corner and in the ending", DAYBREAK["primary"], "#FFB400", AA_TEXT),
    ("ink on the corner's pale sun", DAYBREAK["primary"], "#FFF1C7", AA_TEXT),
]


@pytest.mark.parametrize("role, foreground, background, minimum", PAIRS, ids=[p[0] for p in PAIRS])
def test_every_pair_passes(role, foreground, background, minimum):
    assert contrast(foreground, background) >= minimum, role


def test_the_muted_labels_read_on_the_page():
    assert contrast(muted_label_ink(DAYBREAK), PAGE) >= AA_TEXT


def test_the_publish_guard_finds_nothing():
    assert theme_contrast_guard(DAYBREAK).issues == []
    assert theme_contrast_problems(themes["Daybreak"]) == []


# --- the permissions answer ------------------------------------------------------------


async def test_the_permissions_answer_offers_the_preset_only_while_on(
    client, workspace, test_user_cookies, monkeypatch
):
    url = f"/api/v1/workspaces/{workspace.id}/permissions"
    monkeypatch.setattr(settings, "DAYBREAK_PRESET_ENABLED", False)
    answer = (await client.get(url, cookies=test_user_cookies)).json()
    assert answer["offeredGatedPresets"] == []
    monkeypatch.setattr(settings, "DAYBREAK_PRESET_ENABLED", True)
    answer = (await client.get(url, cookies=test_user_cookies)).json()
    assert answer["offeredGatedPresets"] == ["Daybreak"]
