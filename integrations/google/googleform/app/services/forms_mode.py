"""The Google Forms import switch (``GOOGLE_FORMS_IMPORT=on|readonly|off``) on
this service's side: in ``readonly`` and ``off`` nothing here processes
Google Forms data any more (no listing, import, token check or refresh, no
new connection, no stored credential handed out). The Sheets routes and the
deletion of stored credentials are not Google Forms processing and stay.
"""

from http import HTTPStatus

from googleform.app.exceptions import HTTPException
from googleform.config import settings

MODES = ("on", "readonly", "off")


def google_forms_import_mode() -> str:
    mode = (settings.GOOGLE_FORMS_IMPORT or "on").strip().lower()
    # an unknown value is treated as the strictest mode, never as "on"
    return mode if mode in MODES else "off"


async def google_forms_processing_allowed() -> None:
    """Route dependency: 403 in ``readonly``, 410 in ``off``. Runs before the
    route's other dependencies, so no credential is even read."""
    mode = google_forms_import_mode()
    if mode == "off":
        raise HTTPException(
            HTTPStatus.GONE,
            content={
                "code": "google_forms_off",
                "message": "Google Forms import is turned off on this instance.",
            },
        )
    if mode == "readonly":
        raise HTTPException(
            HTTPStatus.FORBIDDEN,
            content={
                "code": "google_forms_readonly",
                "message": "Google Forms import is read-only on this instance.",
            },
        )
