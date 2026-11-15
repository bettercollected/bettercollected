"""The Pigment theme preset and its switch (``APP_THEME_PIGMENT_ENABLED``, the switch
of the second app theme: one switch for both).

On: the preset is offered to the builder's picker, the edit operations, the AI and
the MCP server. Off (the default): none of them knows it, the name is refused as an
unknown preset is, and nothing else changes. A form that stores the theme keeps
rendering, publishing and saving, whatever the switch says. It is not the preset new
forms start with."""

import pytest
from common.models.standard_form import (
    THEME_ARTWORKS,
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
    NEW_FORM_THEME,
    PICTURE_ARTWORKS,
    PRESET_WELCOME_LAYOUTS,
    artwork_offered,
    get_themes_for_ai,
    offered_presets,
    preset_name,
    preset_offered,
    theme_dict,
    themes,
)
from backend.app.services.ai.ops import apply_form_ops, parse_ops
from backend.app.services.ai.prompt_builder import _looks_guide, ops_guide
from backend.app.services.publish_checks import theme_contrast_problems
from backend.app.services.theme_contrast import (
    AA_NON_TEXT,
    AA_TEXT,
    contrast,
    muted_label_ink,
    theme_contrast_guard,
)
from backend.config import settings

PIGMENT = theme_dict["Pigment"]


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


# --- the switch is the app theme's, off by default ------------------------------------------------


def test_the_preset_follows_the_app_theme_switch_which_is_off_by_default():
    assert GATED_PRESETS["Pigment"] == "app_theme.ENABLED"
    assert type(settings.app_theme).model_fields["ENABLED"].default is False
    assert GATED_ARTWORKS["pigment"] == "Pigment"
    assert "pigment" in THEME_ARTWORKS


def test_it_is_not_the_default_for_new_forms():
    assert NEW_FORM_THEME == "Leaflet"


# --- off: an unknown preset in every reader --------------------------------------------------------


@pytest.mark.parametrize("name", ["Pigment", "pigment", "  PIGMENT "])
def test_off_the_name_means_no_preset(switch_off, name):
    assert preset_name(name) is None


def test_off_it_is_not_offered_or_listed(switch_off):
    assert not preset_offered("Pigment") and not artwork_offered("pigment")
    assert "Pigment" not in offered_presets()
    assert "Pigment" not in [entry["name"] for entry in get_themes_for_ai()]
    assert "Pigment" not in _looks_guide() and "Pigment" not in ops_guide()


def test_off_set_theme_preset_refuses_it_as_it_refuses_an_unknown_name(switch_off):
    _, unknown = _apply(_form(), {"op": "set_theme_preset", "name": "Neon"})
    after, refused = _apply(_form(), {"op": "set_theme_preset", "name": "Pigment"})
    assert not refused[0].ok
    assert refused[0].message == unknown[0].message.replace("Neon", "Pigment")
    assert "Pigment" not in refused[0].message.split("Pick one of:")[1]
    assert after.theme is None


def test_off_a_form_that_stores_the_theme_still_edits_and_passes_the_publish_checks(switch_off):
    after, results = _apply(
        _form(PIGMENT), {"op": "update_field", "fieldId": "q1", "patch": {"title": "Full name"}}
    )
    assert results[0].ok, results[0].message
    assert (after.theme.title, after.theme.choiceKeys) == ("Pigment", "letters")
    assert after.theme.background.artwork == "pigment"
    assert theme_problems(after.theme) == []
    assert theme_contrast_problems(after.theme) == []


# --- on: offered everywhere ----------------------------------------------------------------------


def test_on_it_is_offered(switch_on):
    assert preset_name("pigment") == "Pigment"
    assert "Pigment" in offered_presets()
    assert "Pigment" in [entry["name"] for entry in get_themes_for_ai()]
    assert '- "Pigment": ' in _looks_guide() and '- "Pigment": ' in ops_guide()


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
    after, results = _apply(form, {"op": "set_theme_preset", "name": "pigment"})
    assert results[0].ok, results[0].message
    theme = after.theme
    assert (theme.title, theme.accent, theme.secondary) == ("Pigment", "#FBF7F1", "#4B35DB")
    assert (theme.style, theme.choiceKeys, theme.background.artwork) == ("classic", "letters", "pigment")
    assert (theme.titleFont, theme.radius) == ("besley", "soft")
    assert theme.highlight is None


def test_picking_another_preset_replaces_the_keys_and_the_scene(switch_on):
    after, results = _apply(_form(PIGMENT), {"op": "set_theme_preset", "name": "Ocean"})
    assert results[0].ok and after.theme.choiceKeys is None and after.theme.background is None


def test_it_does_not_change_the_welcome_layout_by_itself(switch_on):
    assert "Pigment" not in PRESET_WELCOME_LAYOUTS
    assert "pigment" not in PICTURE_ARTWORKS


# --- contrast ------------------------------------------------------------------------------------------

PAGE = PIGMENT["accent"]
INK = PIGMENT["primary"]
PIGMENTS = {"tomato": "#FF8A73", "sun": "#FFC62E", "mint": "#5FD9B0", "sky": "#6BBEF7", "orchid": "#D9A0FF"}
PAIRS = [
    ("questions and text on the page", INK, PAGE, AA_TEXT),
    ("answers in the white input boxes", INK, "#FFFFFF", AA_TEXT),
    ("button text on the action colour", "#FFFFFF", PIGMENT["secondary"], AA_TEXT),
    ("chosen option's white text on the iris row", "#FFFFFF", PIGMENT["secondary"], AA_TEXT),
    ("action colour on the page (progress, focus ring)", PIGMENT["secondary"], PAGE, AA_NON_TEXT),
    ("input borders on the page", PIGMENT["tertiary"], PAGE, AA_NON_TEXT),
    ("input borders on white", PIGMENT["tertiary"], "#FFFFFF", AA_NON_TEXT),
    # the rule is the iris (the button colour), not a red: a red beside a question reads as an error
    ("the 'why we ask' rule on the page (iris, 7.0:1)", PIGMENT["secondary"], PAGE, AA_NON_TEXT),
    ("ink on the sun-yellow band (back, page count)", INK, PIGMENTS["sun"], AA_TEXT),
    ("the check's white on the iris disc", "#FFFFFF", PIGMENT["secondary"], AA_TEXT),
    *[(f"key letter ink on {name}", INK, fill, AA_TEXT) for name, fill in PIGMENTS.items()],
]


@pytest.mark.parametrize("role, foreground, background, minimum", PAIRS, ids=[p[0] for p in PAIRS])
def test_every_pair_passes(role, foreground, background, minimum):
    assert contrast(foreground, background) >= minimum, role


def test_the_muted_labels_read_on_the_page():
    assert contrast(muted_label_ink(PIGMENT), PAGE) >= AA_TEXT


def test_the_publish_guard_finds_nothing():
    assert theme_contrast_guard(PIGMENT).issues == []
    assert theme_contrast_problems(themes["Pigment"]) == []


# --- the ink on the yellow band ------------------------------------------------------------------------
# A Pigment theme draws the header bar as the sun-yellow band, always the same yellow, with the
# questions' ink on it. The guard measures `primary` on the band (issue key `band`, shared cases in
# docs/spec/theme-contrast.cases.json) and the webapp falls back to a dark ink where it does not read.

LOW_BAND = {**PIGMENT, "primary": "#6E6585"}  # 5.1:1 on the cream page, 3.46:1 on the band


def test_the_guard_reports_the_band_pair_for_a_primary_that_reads_on_the_page_but_not_on_the_band():
    assert contrast(LOW_BAND["primary"], PAGE) >= AA_TEXT
    assert contrast(LOW_BAND["primary"], PIGMENTS["sun"]) < AA_TEXT
    guard = theme_contrast_guard(LOW_BAND)
    assert [(issue.key, issue.minimum) for issue in guard.issues] == [("band", AA_TEXT)]
    assert round(guard.issues[0].ratio, 2) == 3.46
    # the nearest passing ink keeps its hue and reads on the page and on the band
    assert guard.fix is not None and set(guard.fix) == {"primary"}
    assert contrast(guard.fix["primary"], PAGE) >= AA_TEXT
    assert contrast(guard.fix["primary"], PIGMENTS["sun"]) >= AA_TEXT


def test_the_publish_message_names_the_band():
    problems = theme_contrast_problems(LOW_BAND)
    assert len(problems) == 1
    assert "text on the yellow band of the Pigment look (3.4:1, needs 4.5:1)" in problems[0]["message"]


def test_the_band_is_measured_only_with_the_pigment_artwork():
    plain = {**LOW_BAND, "background": {"type": "color"}}
    assert theme_contrast_guard(plain).issues == []


def test_the_preset_keeps_its_ink_on_the_band():
    assert contrast(PIGMENT["primary"], PIGMENTS["sun"]) >= AA_TEXT
    assert theme_contrast_guard(PIGMENT).issues == []


# --- the permissions answer ------------------------------------------------------------------------------


async def test_the_permissions_answer_offers_the_preset_only_while_the_app_theme_switch_is_on(
    client, workspace, test_user_cookies, monkeypatch
):
    url = f"/api/v1/workspaces/{workspace.id}/permissions"
    monkeypatch.setattr(settings.app_theme, "ENABLED", False)
    answer = (await client.get(url, cookies=test_user_cookies)).json()
    assert "Pigment" not in answer["offeredGatedPresets"]
    monkeypatch.setattr(settings.app_theme, "ENABLED", True)
    answer = (await client.get(url, cookies=test_user_cookies)).json()
    assert "Pigment" in answer["offeredGatedPresets"]
    assert answer["appThemeEnabled"] is True
