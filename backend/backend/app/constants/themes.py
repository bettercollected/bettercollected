# Theme colors dictionary
from common.models.standard_form import Theme

# How a form can be dressed, independent of its colours. Same list as the
# webapp's THEME_STYLES (webapp/src/constants/theme.ts); a parity test keeps
# them together.
THEME_STYLES = ("classic", "sheet", "studio", "leaflet")

theme_dict = {
    # Same values as the webapp's Default preset (webapp/src/constants/theme.ts,
    # DESIGN.md §9), so AI-created forms match forms created in the builder.
    "Default": {
        "title": "Default",
        "primary": "#101828",
        "secondary": "#1649E2",
        "tertiary": "#818CA0",
        "accent": "#F5F7FB",
    },
    # Same values as the webapp's Leaflet preset; picking it also switches the
    # form to the Leaflet style it was made for. New forms start with it
    # (NEW_FORM_THEME below).
    "Leaflet": {
        "title": "Leaflet",
        "primary": "#1A1A1A",
        "secondary": "#0B3D91",
        "tertiary": "#6B7A99",
        "accent": "#FFFFFF",
        "style": "leaflet",
    },
    "Blue": {
        "title": "Blue",
        "primary": "#2E2E2E",
        "secondary": "#337FC2",
        "tertiary": "#61A9E9",
        "accent": "#B0DAFF",
    },
    "Green": {
        "title": "Green",
        "primary": "#2E2E2E",
        "secondary": "#459E73",
        "tertiary": "#81D8AE",
        "accent": "#D7F6E7",
    },
    "Red": {
        "title": "Red",
        "primary": "#2E2E2E",
        "secondary": "#BE3032",
        "tertiary": "#E75759",
        "accent": "#FFB2B3",
    },
    "Black": {
        "title": "Black",
        "primary": "#2E2E2E",
        "secondary": "#2E2E2E",
        "tertiary": "#DBDBDB",
        "accent": "#FFFFFF",
    },
    "Orange": {
        "title": "Orange",
        "primary": "#2E2E2E",
        "secondary": "#DA8C0B",
        "tertiary": "#F1B85A",
        "accent": "#FFEFCC",
    },
    "Purple": {
        "title": "Purple",
        "primary": "#2E2E2E",
        "secondary": "#533CAF",
        "tertiary": "#846BEC",
        "accent": "#CFC3FF",
    },
}

# Descriptions guide the AI on which theme best fits a given form
theme_descriptions = {
    "Leaflet": (
        "The default for new forms: a white sheet with deep navy section bars, "
        "numbered sections and questions, set like a plain-language information "
        "leaflet. Calm and easy to follow for any form; use it unless the "
        "request asks for other colours or a particular mood."
    ),
    "Default": (
        "A clean blue-accented theme. Versatile and professional — ideal for general "
        "surveys, feedback forms, job applications, and corporate questionnaires."
    ),
    "Blue": (
        "A calm, trust-inspiring blue palette. Best for healthcare forms, patient intake, "
        "financial questionnaires, insurance forms, and any context where reliability and "
        "professionalism are important."
    ),
    "Green": (
        "A fresh, growth-oriented green palette. Great for wellness check-ins, "
        "sustainability surveys, environmental feedback, health assessments, and "
        "non-profit / charity forms."
    ),
    "Red": (
        "A bold, urgent red palette. Suited for emergency contact forms, incident reports, "
        "urgent feedback, security audits, and forms that need to command attention quickly."
    ),
    "Black": (
        "A sleek, minimal black-and-white palette conveying elegance and seriousness. "
        "Perfect for luxury brand surveys, creative agency briefs, portfolio intake forms, "
        "and premium product registration."
    ),
    "Orange": (
        "A warm, energetic orange palette. Works well for event registrations, food & "
        "beverage surveys, retail feedback, marketing campaigns, and any form where "
        "enthusiasm and energy should be conveyed."
    ),
    "Purple": (
        "A creative, modern purple palette. Ideal for educational quizzes, academic "
        "research surveys, tech product feedback, onboarding questionnaires, and forms "
        "targeting a younger or creative audience."
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
