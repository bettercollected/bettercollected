"""What the Open Formulieren switches allow.

``OPEN_FORMULIEREN_IMPORT``:

* ``off`` (default): the import endpoints answer 410 ``open_formulieren_off``
  and the providers list does not offer the import.
* ``on``: the import works.

``OPEN_FORMULIEREN_EXPORT`` (own switch, same default and same 410 code):

* ``off`` (default): the export endpoint answers 410 and the providers list
  does not offer it.
* ``on``: a form can be downloaded as an Open Formulieren import archive.

Both are read at call time from ``settings.open_formulieren``.
"""

import enum
from http import HTTPStatus

from backend.app.exceptions import HTTPException
from backend.config import settings

OFF_CODE = "open_formulieren_off"
OFF_MESSAGE = "Importing Open Formulieren forms is turned off on this instance."
EXPORT_OFF_MESSAGE = "Exporting for Open Formulieren is turned off on this instance."
# the providers list entry (GET /providers)
PROVIDER_NAME = "open_formulieren"


class OpenFormulierenImport(str, enum.Enum):
    ON = "on"
    OFF = "off"


def open_formulieren_import_mode() -> OpenFormulierenImport:
    return OpenFormulierenImport(settings.open_formulieren.IMPORT)


def open_formulieren_import_enabled() -> bool:
    return open_formulieren_import_mode() is OpenFormulierenImport.ON


def open_formulieren_export_enabled() -> bool:
    return OpenFormulierenImport(settings.open_formulieren.EXPORT) is OpenFormulierenImport.ON


def refuse_open_formulieren_import() -> None:
    """410 unless the import is on. Called before anything else happens
    (before the body is read or the caller's membership is checked)."""
    if not open_formulieren_import_enabled():
        raise HTTPException(
            HTTPStatus.GONE, content={"code": OFF_CODE, "message": OFF_MESSAGE}
        )


def refuse_open_formulieren_export() -> None:
    """410 unless the export is on: answered before the caller's membership
    or the form is looked at."""
    if not open_formulieren_export_enabled():
        raise HTTPException(
            HTTPStatus.GONE,
            content={"code": OFF_CODE, "message": EXPORT_OFF_MESSAGE},
        )
