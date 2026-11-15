# Theme colors dictionary
from typing import Any, Optional

from common.models.standard_form import THEME_ARTWORKS, Theme

# How a form can be dressed, independent of its colours. Same list as the
# webapp's THEME_STYLES (webapp/src/constants/theme.ts); a parity test keeps
# them together.
THEME_STYLES = ("classic", "sheet", "studio", "leaflet")

# The theme presets, in the order the builder's picker lists them. The
# webapp's ThemeColors (webapp/src/constants/theme.ts) is the source of truth:
# names, colours and styles are what creators see there, so a preset the AI
# picks shows as that preset in the builder. Each service ships on its own
# (separate images), so the list lives on both sides and
# tests/app/services/test_theme_presets.py fails when they drift.
theme_dict = {
    "Default": {
        "title": "Default",
        "primary": "#101828",
        "secondary": "#1649E2",
        "tertiary": "#818CA0",
        "accent": "#F5F7FB",
    },
    "Paper": {
        "title": "Paper",
        "primary": "#292524",
        "secondary": "#7C2D12",
        "tertiary": "#78716C",
        "accent": "#FAF6F0",
    },
    # Picking it also switches the form to the Leaflet style it was made for.
    # New forms start with it (NEW_FORM_THEME below).
    "Leaflet": {
        "title": "Leaflet",
        "primary": "#1A1A1A",
        "secondary": "#0B3D91",
        "tertiary": "#6B7A99",
        "accent": "#FFFFFF",
        "style": "leaflet",
    },
    "Ocean": {
        "title": "Ocean",
        "primary": "#111827",
        "secondary": "#1D4ED8",
        "tertiary": "#2563EB",
        "accent": "#DBEAFE",
    },
    "Forest": {
        "title": "Forest",
        "primary": "#052E16",
        "secondary": "#15803D",
        "tertiary": "#16A34A",
        "accent": "#DCFCE7",
    },
    "Cherry": {
        "title": "Cherry",
        "primary": "#450A0A",
        "secondary": "#B91C1C",
        "tertiary": "#DC2626",
        "accent": "#FEE2E2",
    },
    "Mono": {
        "title": "Mono",
        "primary": "#101826",
        "secondary": "#101826",
        "tertiary": "#767676",
        "accent": "#FFFFFF",
    },
    "Sunset": {
        "title": "Sunset",
        "primary": "#431407",
        "secondary": "#C2410C",
        "tertiary": "#EA580C",
        "accent": "#FFEDD5",
    },
    "Lavender": {
        "title": "Lavender",
        "primary": "#3B0764",
        "secondary": "#7E22CE",
        "tertiary": "#9333EA",
        "accent": "#F3E8FF",
    },
    "Slate": {
        "title": "Slate",
        "primary": "#111827",
        "secondary": "#4B5563",
        "tertiary": "#64748B",
        "accent": "#F3F4F6",
    },
    "Blossom": {
        "title": "Blossom",
        "primary": "#500724",
        "secondary": "#BE185D",
        "tertiary": "#DB2777",
        "accent": "#FCE7F3",
    },
    "Twilight": {
        "title": "Twilight",
        "primary": "#1E1B4B",
        "secondary": "#4338CA",
        "tertiary": "#4F46E5",
        "accent": "#E0E7FF",
    },
    "Honey": {
        "title": "Honey",
        "primary": "#422006",
        "secondary": "#A16207",
        "tertiary": "#B45309",
        "accent": "#FEF3C7",
    },
    "Mint": {
        "title": "Mint",
        "primary": "#042F2E",
        "secondary": "#0F766E",
        "tertiary": "#0D9488",
        "accent": "#CCFBF1",
    },
    "Sky": {
        "title": "Sky",
        "primary": "#083344",
        "secondary": "#0E7490",
        "tertiary": "#0891B2",
        "accent": "#CFFAFE",
    },
    "Rose": {
        "title": "Rose",
        "primary": "#4C0519",
        "secondary": "#BE123C",
        "tertiary": "#E11D48",
        "accent": "#FFE4E6",
    },
    # Complete looks: colours, faces, corners, buttons and background in one
    # pick. They set every type and shape key, so nothing of the previous
    # look stays behind; picking one also sets the welcome page's layout
    # (PRESET_WELCOME_LAYOUTS below).
    "Kantlijn": {
        "title": "Kantlijn",
        "primary": "#16261F",
        "secondary": "#1E4D3B",
        "tertiary": "#7D8C84",
        "accent": "#F8EEEC",
        "style": "classic",
        "titleFont": "besley",
        "bodyFont": "atkinson-next",
        "dataFont": "atkinson-mono",
        "titleWidth": "normal",
        "radius": "soft",
        "buttonStyle": "filled",
        "highlight": "#A3305A",
        "selection": "#1E4D3B",
        "background": {
            "type": "pattern",
            "pattern": "margin",
            "artwork": "marble",
        },
    },
    "Raster": {
        "title": "Raster",
        "primary": "#0E0E14",
        "secondary": "#2B2FD1",
        "tertiary": "#6D7083",
        "accent": "#FFFFFF",
        "style": "studio",
        "titleFont": "archivo",
        "bodyFont": "archivo",
        "dataFont": "atkinson-mono",
        "titleWidth": "expanded",
        "radius": "sharp",
        "buttonStyle": "outlined",
        "background": {
            "type": "pattern",
            "pattern": "columns",
        },
    },
    # A scene preset: the Default preset's blue on a periwinkle page, a sun in
    # the corner of the page and a sunrise on the ending (background.artwork
    # "daybreak", drawn by the webapp). Colours only: it keeps the form's
    # faces, corners and buttons. Offered while DAYBREAK_PRESET_ENABLED is on
    # (GATED_PRESETS below).
    "Daybreak": {
        "title": "Daybreak",
        "primary": "#0E1737",
        "secondary": "#1649E2",
        "tertiary": "#6E7CA8",
        "accent": "#F3F6FF",
        "style": "classic",
        "background": {
            "type": "color",
            "artwork": "daybreak",
        },
    },
    # A scene preset: iris on warm cream paper, a sun-yellow band over the questions,
    # lettered answer keys in five flat pigments and, on the ending, five flat shapes
    # that pop around the check (background.artwork "pigment", drawn by the webapp).
    # Colours and the scene only: faces, corners and buttons stay the form's own.
    # Offered while APP_THEME_PIGMENT_ENABLED is on (GATED_PRESETS below).
    "Pigment": {
        "title": "Pigment",
        "primary": "#1A1238",
        "secondary": "#4B35DB",
        "tertiary": "#7C7396",
        "accent": "#FBF7F1",
        "style": "classic",
        "choiceKeys": "letters",
        "background": {
            "type": "color",
            "artwork": "pigment",
        },
    },
}

# Presets that are offered only while their switch (a backend setting) is on.
# `theme_dict` always lists them, so the two sides stay in step and a form that
# stores one keeps rendering; what the switch decides is whether the name is
# *offered*: by the builder's picker (the permissions answer carries it), by the
# edit operations, the AI and the MCP server, which refuse an unoffered name as
# they refuse an unknown one. A later preset joins here with its own switch.
# The value names the backend setting (an attribute of ``backend.config.settings``,
# dotted for a settings group): the Pigment preset follows the app theme switch.
GATED_PRESETS = {
    "Daybreak": "DAYBREAK_PRESET_ENABLED",
    "Pigment": "app_theme.ENABLED",
}

# Artwork that fills the picture half of a welcome or ending page (a page set
# beside an image). Other artwork (the Daybreak scene) is drawn on the page
# itself and does not change a page's layout.
PICTURE_ARTWORKS = ("marble",)

# The welcome page layout a complete-look preset is made for. Same list as
# the webapp's PRESET_WELCOME_LAYOUTS (webapp/src/constants/theme.ts); a test
# keeps them together. set_theme_preset applies it to a welcome page without
# an image of its own (ops.py).
PRESET_WELCOME_LAYOUTS = {
    "Kantlijn": "TWO_COLUMN_IMAGE_RIGHT",
    "Raster": "SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN",
}

# The names the backend's presets had before they followed the webapp, each
# with the nearest preset now. Models may still use them (older prompts,
# stored replies, habit), so they keep working.
LEGACY_PRESET_NAMES = {
    "Blue": "Ocean",
    "Green": "Forest",
    "Red": "Cherry",
    "Black": "Mono",
    "Orange": "Sunset",
    "Purple": "Lavender",
}

# Descriptions guide the AI on which theme best fits a given form. The first
# sentence is what the chat's guide shows (prompt_builder._looks_guide).
theme_descriptions = {
    "Leaflet": (
        "The default for new forms: a white sheet with deep navy section bars, "
        "numbered sections and questions, set like a plain-language information "
        "leaflet. Calm and easy to follow for any form; use it unless the "
        "request asks for other colours or a particular mood."
    ),
    "Default": (
        "A clean blue-accented theme on a soft grey ground. Versatile and "
        "professional: general surveys, feedback forms, job applications and "
        "corporate questionnaires."
    ),
    "Paper": (
        "Warm cream paper with espresso ink, like a printed page. Suits letters, "
        "applications, literary or heritage organisations and forms that should "
        "feel personal and considered."
    ),
    "Ocean": (
        "A calm, trust-inspiring blue palette. Best for healthcare forms, patient "
        "intake, financial questionnaires, insurance forms, and any context where "
        "reliability and professionalism are important."
    ),
    "Forest": (
        "A fresh, growth-oriented green palette. Great for wellness check-ins, "
        "sustainability surveys, environmental feedback, health assessments, and "
        "non-profit or charity forms."
    ),
    "Cherry": (
        "A bold, urgent red palette. Suited for emergency contact forms, incident "
        "reports, urgent feedback, security audits, and forms that need to command "
        "attention quickly."
    ),
    "Mono": (
        "A sleek, minimal black-and-white palette conveying elegance and "
        "seriousness. Perfect for creative agency briefs, portfolio intake forms, "
        "premium product registration and formal documents."
    ),
    "Sunset": (
        "A warm, energetic orange palette. Works well for event registrations, "
        "food and beverage surveys, retail feedback, marketing campaigns, and any "
        "form where enthusiasm and energy should be conveyed."
    ),
    "Lavender": (
        "A creative, modern purple palette. Ideal for educational quizzes, academic "
        "research surveys, tech product feedback, onboarding questionnaires, and "
        "forms for a younger or creative audience."
    ),
    "Slate": (
        "A quiet grey palette, neutral and businesslike. Good for internal "
        "requests, IT and facilities forms, audits, and anything that should stay "
        "out of the way."
    ),
    "Blossom": (
        "A soft, friendly pink palette. Fits celebrations, weddings, beauty and "
        "lifestyle feedback, community events and warm, personal invitations."
    ),
    "Twilight": (
        "A deep indigo palette, thoughtful and modern. Suits technology, research, "
        "conferences, evening events and product feedback."
    ),
    "Honey": (
        "A warm amber palette, welcoming and down to earth. Good for food, "
        "hospitality, farms and markets, volunteering and neighbourhood forms."
    ),
    "Mint": (
        "A cool teal-green palette, clean and refreshing. Fits care and wellbeing, "
        "clinic forms, cleaning and home services, and outdoor activities."
    ),
    "Sky": (
        "A bright cyan palette, open and airy. Suits travel, water sports, "
        "transport, summer programmes and light, upbeat surveys."
    ),
    "Rose": (
        "A rich rose-red palette, warm and confident. Good for fundraising, "
        "memberships, arts and culture, and campaigns that should feel heartfelt."
    ),
    "Kantlijn": (
        "A complete look like a well-made small-press book: serif titles, a "
        "cloth-green action colour, rose margin notes and a marbled endpaper "
        "beside the welcome page. Suits associations, culture, heritage, "
        "volunteering and forms that should feel crafted and personal."
    ),
    "Raster": (
        "A complete look like a Swiss poster: large expanded titles on a "
        "visible column grid, square edges, outlined buttons and one "
        "ultramarine for the respondent's own answers. Suits design, "
        "architecture, events, research and confident, modern organisations."
    ),
    "Daybreak": (
        "The blue you know with the sun coming up behind it: a soft periwinkle "
        "page, a small sun in the corner and a sun rising over two hills on the "
        "ending. Calm and friendly; suits community, health, education and "
        "neighbourhood forms that should feel welcoming."
    ),
    "Pigment": (
        "Iris on warm cream paper with a sun-yellow band over the questions, "
        "answer keys in five flat colours with their letters, and five flat "
        "shapes that pop around the check when the form is sent. Lively and "
        "friendly; suits associations, schools, events and community forms."
    ),
}

themes = {title: Theme(**colors) for title, colors in theme_dict.items()}

# The theme every new form starts with when it brings none of its own: a
# blank form, an AI-created one, one made through the API or MCP, a PDF
# import without brand colours, a Google Forms or Typeform import. A form
# made from a template and a copy keep their source's theme, and stored
# forms never change (their theme is stored inline). The webapp's blank form
# uses the same preset (webapp/src/constants/theme.ts NEW_FORM_THEME); a test
# keeps the two together.
NEW_FORM_THEME = "Leaflet"


def new_form_theme() -> Theme:
    """A fresh copy of the theme new forms start with."""
    return themes[NEW_FORM_THEME].model_copy(deep=True)


_PRESET_NAMES_BY_KEY = {
    **{legacy.lower(): name for legacy, name in LEGACY_PRESET_NAMES.items()},
    **{name.lower(): name for name in theme_dict},
}


def preset_offered(name: str) -> bool:
    """Is the preset (its own name) offered: it has no switch, or its switch
    (GATED_PRESETS, a backend setting) is on? A form that stores an unoffered
    preset still renders and saves; only picking it anew is refused."""
    switch = GATED_PRESETS.get(name)
    return True if switch is None else switch_on(switch)


def switch_on(switch: str) -> bool:
    """Is a backend setting on? ``switch`` is a setting's name, or a dotted
    name for one in a settings group (``app_theme.ENABLED``)."""
    from backend.config import settings

    value: Any = settings
    for part in switch.split("."):
        value = getattr(value, part, False)
    return bool(value)


# Theme keys that are offered while a switch is on: a new theme that sets one
# (any value) while it is off is refused as a gated artwork is, unless the
# stored theme at the same place already has it. The choice keys belong to the
# Pigment theme, so they follow its one switch (APP_THEME_PIGMENT_ENABLED).
GATED_THEME_KEYS = {
    "choiceKeys": "app_theme.ENABLED",
}


def theme_key_offered(key: str) -> bool:
    """Is the theme key (``GATED_THEME_KEYS``) offered now: it has no switch,
    or its switch is on?"""
    switch = GATED_THEME_KEYS.get(key)
    return True if switch is None else switch_on(switch)


def offered_theme_keys() -> list[str]:
    """The gated theme keys a new theme may set now."""
    return [key for key in GATED_THEME_KEYS if theme_key_offered(key)]


# Artwork that belongs to a gated preset: it is offered while that preset is.
# Anything that takes an inline theme (a form save, the edit operations, a saved
# workspace theme) refuses a new theme that names an artwork that is not offered,
# as it refuses an unlisted one, unless the stored value already has it.
GATED_ARTWORKS = {
    "daybreak": "Daybreak",
    "pigment": "Pigment",
}


def artwork_offered(artwork: Optional[str]) -> bool:
    """Is the artwork (a ``background.artwork`` value) offered now: it is on no
    gated preset's list, or its preset is offered (``preset_offered``)?"""
    preset = GATED_ARTWORKS.get(artwork) if isinstance(artwork, str) else None
    return preset is None or preset_offered(preset)


def offered_artworks() -> list[str]:
    """The ``background.artwork`` values a new theme may name now."""
    return [artwork for artwork in THEME_ARTWORKS if artwork_offered(artwork)]


def offered_presets() -> list[str]:
    """The presets' names that are offered now, in the picker's order."""
    return [name for name in theme_dict if preset_offered(name)]


def preset_name(name: Optional[str]) -> Optional[str]:
    """The preset a name means, in any case and with surrounding spaces: a
    preset's own name, or a legacy name (LEGACY_PRESET_NAMES) for the nearest
    preset. None when the name means no preset, or a preset that is not
    offered (its switch is off): it is refused as an unknown one is."""
    if not isinstance(name, str):
        return None
    found = _PRESET_NAMES_BY_KEY.get(name.strip().lower())
    return found if found is not None and preset_offered(found) else None


def get_themes_for_ai() -> list[dict]:
    """Return the offered themes with descriptions for use in AI tool calls."""
    result = []
    for name, colors in theme_dict.items():
        if not preset_offered(name):
            continue
        result.append(
            {
                "name": name,
                "description": theme_descriptions.get(name, ""),
                "colors": {
                    "primary": colors["primary"],
                    "secondary": colors["secondary"],
                    "tertiary": colors["tertiary"],
                    "accent": colors["accent"],
                },
            }
        )
    return result
