# Theme colors dictionary
from typing import Optional

from common.models.standard_form import Theme

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


def preset_name(name: Optional[str]) -> Optional[str]:
    """The preset a name means, in any case and with surrounding spaces: a
    preset's own name, or a legacy name (LEGACY_PRESET_NAMES) for the nearest
    preset. None when the name means no preset."""
    if not isinstance(name, str):
        return None
    return _PRESET_NAMES_BY_KEY.get(name.strip().lower())


def get_themes_for_ai() -> list[dict]:
    """Return themes with descriptions for use in AI tool calls."""
    result = []
    for name, colors in theme_dict.items():
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
