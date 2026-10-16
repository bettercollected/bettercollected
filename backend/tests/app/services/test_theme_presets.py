"""The backend's theme presets (used for AI-created forms) match the webapp."""

import re
from pathlib import Path

from backend.app.constants.themes import get_themes_for_ai, themes

WEBAPP_THEME_TS = Path(__file__).resolve().parents[4] / "webapp" / "src" / "constants" / "theme.ts"


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
