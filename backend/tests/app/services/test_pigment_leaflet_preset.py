"""The Pigment Leaflet theme preset (the Leaflet style in the Pigment look) and its switch.

It names the Pigment artwork and the choice keys, so it follows the same one switch as the
Pigment preset (``APP_THEME_PIGMENT_ENABLED``): no switch of its own. On: offered to the
builder's picker, the edit operations, the AI and the MCP server. Off (the default): none of
them knows it, the name is refused as an unknown preset is. A form that stores the theme keeps
rendering, publishing and saving, whatever the switch says. It is not the preset new forms
start with. The webapp draws its section bar as the sun-yellow band (style ``leaflet`` and
artwork ``pigment``); the guard measures the ink on that band as for every Pigment theme."""

import pytest
from common.models.standard_form import (
    StandardFieldProperty,
    StandardForm,
    StandardFormField,
    StandardFormFieldType as T,
    Theme,
    theme_problems,
)

from backend.app.constants.themes import (
    GATED_ARTWORKS,
    GATED_PRESETS,
    GATED_THEME_KEYS,
    NEW_FORM_THEME,
    PIGMENT_LEAFLET_PRESET,
    PRESET_WELCOME_LAYOUTS,
    artwork_offered,
    get_themes_for_ai,
    offered_presets,
    preset_name,
    preset_offered,
    theme_descriptions,
    theme_dict,
    themes,
)
from backend.app.services.ai.ops import apply_form_ops, parse_ops
from backend.app.services.ai.prompt_builder import _looks_guide, ops_guide
from backend.app.services.publish_checks import theme_contrast_problems
from backend.app.services.theme_contrast import (
    AA_NON_TEXT,
    AA_TEXT,
    PIGMENT_BAND,
    PIGMENT_BAND_TINT,
    contrast,
    has_pigment_band,
    theme_contrast_guard,
)
from backend.config import settings

NAME = "Pigment Leaflet"
BLEND = theme_dict[NAME]
PIGMENT = theme_dict["Pigment"]
LEAFLET = theme_dict["Leaflet"]


@pytest.fixture
def switch_on(monkeypatch):
    monkeypatch.setattr(settings.app_theme, "ENABLED", True)


@pytest.fixture
def switch_off(monkeypatch):
    monkeypatch.setattr(settings.app_theme, "ENABLED", False)


def _form(theme=None) -> StandardForm:
    return StandardForm(
        title="Form",
        theme=Theme(**theme) if isinstance(theme, dict) else theme,
        fields=[
            StandardFormField(
                id="page-1",
                type=T.SLIDE,
                properties=StandardFieldProperty(
                    fields=[StandardFormField(id="q1", index=0, type=T.SHORT_TEXT, title="Your name")]
                ),
            )
        ],
    )


def _apply(form, *ops):
    return apply_form_ops(form, parse_ops(list(ops)), atomic=False)


# --- what it is ------------------------------------------------------------------------------------


def test_the_name_is_one_constant():
    assert PIGMENT_LEAFLET_PRESET == NAME
    assert BLEND["title"] == NAME and NAME in themes and NAME in theme_descriptions


def test_it_is_leaflets_style_in_pigments_colours_keys_and_artwork():
    for key in ("primary", "secondary", "tertiary", "accent", "choiceKeys"):
        assert BLEND[key] == PIGMENT[key]
    assert BLEND["style"] == "leaflet" == LEAFLET["style"]
    assert BLEND["background"] == PIGMENT["background"] == {"type": "color", "artwork": "pigment"}
    # a preset sets colours, style, keys and artwork: faces, corners and buttons stay the form's own
    assert set(BLEND) == {"title", "primary", "secondary", "tertiary", "accent", "style", "choiceKeys", "background"}


def test_it_follows_the_pigment_switch_and_has_none_of_its_own():
    assert GATED_PRESETS[NAME] == GATED_PRESETS["Pigment"] == GATED_THEME_KEYS["choiceKeys"] == "app_theme.ENABLED"
    assert GATED_ARTWORKS["pigment"] == "Pigment"
    assert type(settings.app_theme).model_fields["ENABLED"].default is False


def test_it_is_not_the_default_for_new_forms_and_sets_no_welcome_layout():
    assert NEW_FORM_THEME == "Leaflet"
    assert NAME not in PRESET_WELCOME_LAYOUTS


def test_it_passes_every_writer_check():
    assert theme_problems(BLEND) == []
    assert theme_problems(themes[NAME]) == []


# --- off: an unknown preset in every reader -------------------------------------------------------


@pytest.mark.parametrize("name", [NAME, "pigment leaflet", "  PIGMENT LEAFLET "])
def test_off_the_name_means_no_preset(switch_off, name):
    assert preset_name(name) is None


def test_off_it_is_not_offered_or_listed(switch_off):
    assert not preset_offered(NAME)
    assert NAME not in offered_presets()
    assert NAME not in [entry["name"] for entry in get_themes_for_ai()]
    assert NAME not in _looks_guide() and NAME not in ops_guide()
    # the Pigment preset's switch is the same one, and Leaflet is offered either way
    assert not preset_offered("Pigment") and preset_offered("Leaflet")


def test_off_set_theme_preset_refuses_it_as_it_refuses_an_unknown_name(switch_off):
    _, unknown = _apply(_form(), {"op": "set_theme_preset", "name": "Neon"})
    after, refused = _apply(_form(), {"op": "set_theme_preset", "name": NAME})
    assert not refused[0].ok
    assert refused[0].message == unknown[0].message.replace("Neon", NAME)
    assert NAME not in refused[0].message.split("Pick one of:")[1]
    assert after.theme is None


def test_off_a_form_that_stores_the_theme_still_edits_and_passes_the_publish_checks(switch_off):
    after, results = _apply(_form(BLEND), {"op": "update_field", "fieldId": "q1", "patch": {"title": "Full name"}})
    assert results[0].ok, results[0].message
    assert (after.theme.title, after.theme.style, after.theme.choiceKeys) == (NAME, "leaflet", "letters")
    assert after.theme.background.artwork == "pigment"
    assert theme_problems(after.theme) == []
    assert theme_contrast_problems(after.theme) == []


# --- on: offered everywhere -------------------------------------------------------------------------


def test_on_it_is_offered(switch_on):
    assert preset_name("pigment leaflet") == NAME
    assert NAME in offered_presets()
    assert NAME in [entry["name"] for entry in get_themes_for_ai()]
    assert f'- "{NAME}": ' in _looks_guide() and f'- "{NAME}": ' in ops_guide()


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
    after, results = _apply(form, {"op": "set_theme_preset", "name": "pigment leaflet"})
    assert results[0].ok, results[0].message
    theme = after.theme
    assert (theme.title, theme.accent, theme.secondary) == (NAME, "#FBF7F1", "#4B35DB")
    assert (theme.style, theme.choiceKeys, theme.background.artwork) == ("leaflet", "letters", "pigment")
    assert (theme.titleFont, theme.radius) == ("besley", "soft")
    assert theme.highlight is None


def test_picking_another_preset_replaces_the_style_the_keys_and_the_scene(switch_on):
    after, results = _apply(_form(BLEND), {"op": "set_theme_preset", "name": "Ocean"})
    assert results[0].ok and after.theme.choiceKeys is None and after.theme.background is None


def test_the_other_presets_are_untouched(switch_on):
    assert theme_dict["Pigment"]["style"] == "classic" and theme_dict["Leaflet"]["style"] == "leaflet"
    assert "choiceKeys" not in LEAFLET and "background" not in LEAFLET


# --- contrast: the colours are Pigment's, plus the bar ----------------------------------------------

PAGE = BLEND["accent"]
INK = BLEND["primary"]
PAIRS = [
    ("questions and text on the page", INK, PAGE, AA_TEXT),
    ("button text on the action colour", "#FFFFFF", BLEND["secondary"], AA_TEXT),
    ("question numerals in iris on the page", BLEND["secondary"], PAGE, AA_TEXT),
    ("the margin note's iris rule on the page", BLEND["secondary"], PAGE, AA_NON_TEXT),
    ("input borders on the page", BLEND["tertiary"], PAGE, AA_NON_TEXT),
    ("the section bar's ink on the sun band", INK, PIGMENT_BAND, AA_TEXT),
    ("the intro band's ink on the sun tint", INK, PIGMENT_BAND_TINT, 7.0),
]


@pytest.mark.parametrize("role, foreground, background, minimum", PAIRS, ids=[p[0] for p in PAIRS])
def test_every_pair_passes(role, foreground, background, minimum):
    assert contrast(foreground, background) >= minimum, role


def test_the_band_colours_are_the_webapps():
    assert (PIGMENT_BAND, PIGMENT_BAND_TINT) == ("#FFC62E", "#FFF0C2")


def test_the_guard_measures_the_ink_on_the_bar_as_on_the_band():
    # the bar wears the band colour, so the existing band rule covers it: a Leaflet theme with the Pigment artwork is measured
    assert has_pigment_band(BLEND) and has_pigment_band(PIGMENT) and not has_pigment_band(LEAFLET)
    assert theme_contrast_guard(BLEND).issues == []
    assert theme_contrast_problems(themes[NAME]) == []
    low = {**BLEND, "primary": "#6E6585"}  # reads on the page (5.1:1), not on the yellow (3.46:1)
    assert contrast(low["primary"], PAGE) >= AA_TEXT and contrast(low["primary"], PIGMENT_BAND) < AA_TEXT
    assert [(issue.key, issue.minimum) for issue in theme_contrast_guard(low).issues] == [("band", AA_TEXT)]
    # a Leaflet theme without the artwork is not asked for the band
    assert theme_contrast_guard({**low, "background": {"type": "color"}}).issues == []


# --- the permissions answer -------------------------------------------------------------------------


async def test_the_permissions_answer_offers_it_only_while_the_app_theme_switch_is_on(client, workspace, test_user_cookies, monkeypatch):
    url = f"/api/v1/workspaces/{workspace.id}/permissions"
    monkeypatch.setattr(settings.app_theme, "ENABLED", False)
    answer = (await client.get(url, cookies=test_user_cookies)).json()
    assert NAME not in answer["offeredGatedPresets"]
    monkeypatch.setattr(settings.app_theme, "ENABLED", True)
    answer = (await client.get(url, cookies=test_user_cookies)).json()
    assert NAME in answer["offeredGatedPresets"] and "Pigment" in answer["offeredGatedPresets"]
