"""Legacy (non-Unicode) fonts.

Several widely used Devanagari fonts predate Unicode: they draw Devanagari
glyphs over Latin character codes, so a PDF's text layer says "kl/ro" where
the page shows "परिचय". Text in these fonts must be decoded (or read from the
page image); taken at face value it is gibberish.
"""

from __future__ import annotations

import re

# lowercase name fragments; matched against the base font name without the
# subset prefix ("ABCDEF+") and style suffixes
LEGACY_DEVANAGARI_FONTS = (
    "preeti",
    "aakriti",
    "kantipur",
    "himalb",
    "himali",
    "sagarmatha",
    "pcs nepali",
    "pcsnepali",
    "ganess",
    "fontasy himali",
    "kruti dev",
    "krutidev",
    "devlys",
    "walkman-chanakya",
    "chanakya",
)

_SUBSET = re.compile(r"^[A-Z]{6}\+")


def base_font_name(font_name: str) -> str:
    return _SUBSET.sub("", font_name or "")


def is_legacy_font(font_name: str) -> bool:
    name = base_font_name(font_name).lower().replace("_", " ").replace("-", " ")
    compact = name.replace(" ", "")
    return any(
        fragment in name or fragment.replace(" ", "") in compact
        for fragment in LEGACY_DEVANAGARI_FONTS
    )
