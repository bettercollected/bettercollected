"""The server switch of the CSV import, ``CSV_IMPORT_ENABLED`` (default off
until it is released).

Off: every import route answers 404 as if it did not exist, the webapp is told
(``csvImportEnabled`` with the permissions) and shows no control. The hourly
sweep that deletes uploaded files runs either way, so turning the switch off
leaves nothing behind.
"""


def csv_import_enabled() -> bool:
    """Is ``CSV_IMPORT_ENABLED`` on?"""
    from backend.config import settings

    return bool(getattr(settings, "CSV_IMPORT_ENABLED", False))
