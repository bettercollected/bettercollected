"""What the Open Formulieren import switch (``OPEN_FORMULIEREN_IMPORT``) allows.

* ``off`` (default): the import endpoints answer 410 ``open_formulieren_off``
  and the providers list does not offer the import.
* ``on``: the import works.

The mode is read at call time from ``settings.open_formulieren.IMPORT``.
"""

import enum
from http import HTTPStatus

from backend.app.exceptions import HTTPException
from backend.config import settings

OFF_CODE = "open_formulieren_off"
OFF_MESSAGE = "Importing Open Formulieren forms is turned off on this instance."
# the providers list entry (GET /providers)
PROVIDER_NAME = "open_formulieren"


class OpenFormulierenImport(str, enum.Enum):
    ON = "on"
    OFF = "off"


def open_formulieren_import_mode() -> OpenFormulierenImport:
    return OpenFormulierenImport(settings.open_formulieren.IMPORT)


def open_formulieren_import_enabled() -> bool:
    return open_formulieren_import_mode() is OpenFormulierenImport.ON


def refuse_open_formulieren_import() -> None:
    """410 unless the import is on. Called before anything else happens
    (before the body is read or the caller's membership is checked)."""
    if not open_formulieren_import_enabled():
        raise HTTPException(
            HTTPStatus.GONE, content={"code": OFF_CODE, "message": OFF_MESSAGE}
        )
