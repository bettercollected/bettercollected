# Theme colors dictionary
from common.models.standard_form import Theme

theme_dict = {
    "Default": {
        "title": "Default",
        "primary": "#2E2E2E",
        "secondary": "#0764EB",
        "tertiary": "#A2C5F8",
        "accent": "#F2F7FF",
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
