"""What the Google Forms import switch (``GOOGLE_FORMS_IMPORT``) allows.

* ``on``: everything as before.
* ``readonly``: imported forms and their responses stay readable from our
  store, but no Google Forms data is processed any more: no new import, no
  re-sync (an import of an already imported form), no connection or token
  refresh, no listing of the user's Google forms. Refused with 403
  ``google_forms_readonly``. The Google Sheets action and deleting stored
  Google credentials (account deletion) still work: they are not Google Forms
  processing.
* ``off``: the Google Forms endpoints answer 410 ``google_forms_off`` and the
  backend never calls the Google Forms service, for anything (the Sheets
  action included, until it no longer goes through that service).

The mode is read at call time from ``settings.google_forms.IMPORT``.
"""

import enum
import logging
from http import HTTPStatus
from typing import Any

from common.enums.form_provider import FormProvider

from backend.app.exceptions import HTTPException
from backend.config import settings

log = logging.getLogger(__name__)

READONLY_CODE = "google_forms_readonly"
OFF_CODE = "google_forms_off"
READONLY_MESSAGE = (
    "Google Forms import is read-only on this instance: forms and responses "
    "imported earlier stay available here, but new imports and re-syncs from "
    "Google Forms are no longer possible."
)
OFF_MESSAGE = "Google Forms import is turned off on this instance."


class GoogleFormsImport(str, enum.Enum):
    ON = "on"
    READONLY = "readonly"
    OFF = "off"


def google_forms_import_mode() -> GoogleFormsImport:
    return GoogleFormsImport(settings.google_forms.IMPORT)


def is_google(provider: Any) -> bool:
    value = getattr(provider, "value", provider)
    return isinstance(value, str) and value.strip().lower() == FormProvider.GOOGLE.value


def google_service_enabled() -> bool:
    """False in ``off``: nothing may call the Google Forms service."""
    return google_forms_import_mode() is not GoogleFormsImport.OFF


def _off() -> HTTPException:
    return HTTPException(
        HTTPStatus.GONE, content={"code": OFF_CODE, "message": OFF_MESSAGE}
    )


def refuse_google_forms_processing(provider: Any = FormProvider.GOOGLE) -> None:
    """Raise unless Google Forms data may be processed now (mode ``on``):
    imports, re-syncs, listing Google forms, connecting the account and
    anything else that would reach Google with a Google Forms credential.
    Other providers pass."""
    if not is_google(provider):
        return
    mode = google_forms_import_mode()
    if mode is GoogleFormsImport.OFF:
        raise _off()
    if mode is GoogleFormsImport.READONLY:
        raise HTTPException(
            HTTPStatus.FORBIDDEN,
            content={"code": READONLY_CODE, "message": READONLY_MESSAGE},
        )


def refuse_google_service_call(provider: Any = FormProvider.GOOGLE) -> None:
    """Raise 410 in ``off`` before anything calls the Google Forms service
    (``readonly`` still allows the calls that process no Google Forms data)."""
    if is_google(provider) and not google_service_enabled():
        raise _off()
