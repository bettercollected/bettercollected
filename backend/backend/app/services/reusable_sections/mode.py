"""The switch for the workspace library of reusable sections:
``REUSABLE_SECTIONS_ENABLED``.

Off by default (a creator-configurable feature that is not released yet). While
it is off the library's routes answer 404 as if they did not exist, and the
operation that inserts a library section fails. A form that already holds a copy
of a section is not affected: the copy is an ordinary set of questions.
"""

from http import HTTPStatus

from backend.app.exceptions import HTTPException

DISABLED_MESSAGE = (
    "Reusable sections are not available on this server yet "
    "(REUSABLE_SECTIONS_ENABLED is off)."
)


def reusable_sections_enabled() -> bool:
    """Is ``REUSABLE_SECTIONS_ENABLED`` on?"""
    from backend.config import settings

    return bool(getattr(settings, "REUSABLE_SECTIONS_ENABLED", False))


def ensure_enabled() -> None:
    """404 while the switch is off (the library does not exist, as far as a
    caller can tell)."""
    if not reusable_sections_enabled():
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, content="Not found")
