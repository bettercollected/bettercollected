"""The library marker on a copied question (``properties.library``).

It points at a section of one workspace's library, so it means nothing outside
that workspace and nothing to a respondent: a copy to another workspace
(template, import) and the form a respondent is served drop it
(``strip_library_markers``). A duplicate inside the workspace keeps it.
"""

from typing import Any

from backend.app.services.option_sources import read


def strip_library_markers(form: Any) -> int:
    """Remove the marker from every question of ``form``, in place; returns how
    many carried one. Works on models and on plain dicts (snake or camel
    case)."""
    removed = 0
    for field, _ in read.every_field(form):
        properties = read.props(field)
        if properties is None or read.get(properties, "library") is None:
            continue
        if isinstance(properties, dict):
            properties.pop("library", None)
        else:
            properties.library = None
        removed += 1
    return removed
