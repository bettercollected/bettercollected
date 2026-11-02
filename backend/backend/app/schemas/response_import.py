"""Stored records of the CSV import of responses (``services/response_import``):
one row per import, which is also its audit entry and its job state, and the
encrypted upload while it is needed.

The import row never holds an answer, a header, a file name or a question
title: who imported, into which form, how many rows, the state and the outcome
(a code), the mapping as column positions and target keys, and the problems as
``{row, column, code}``. The uploaded file waits in ``response_import_files``,
encrypted for the workspace, form and import, and is deleted when the job ends
(any outcome), when the importer discards it, with the form, and at the latest
``FILE_TTL`` after it was uploaded.
"""

import datetime as dt
import enum
from typing import Any, Dict, List, Optional

from common.records import Record, RecordId
from pydantic import field_validator


def _utc(value: Optional[dt.datetime]) -> Optional[dt.datetime]:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value


# what actor_id becomes when the account is deleted: the audit row stays
DELETED_ACTOR = "deleted-user"


class ImportStatus(str, enum.Enum):
    # the file is uploaded and read; nothing is checked yet
    UPLOADED = "uploaded"
    # a dry run is waiting for / being run by a worker
    CHECKING = "checking"
    # a dry run finished: its results are on the row
    CHECKED = "checked"
    # the import job: waiting, storing, finished
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    # ended without storing anything (or after undoing what it had stored)
    FAILED = "failed"
    CANCELLED = "cancelled"
    # the responses were deleted again by the importer
    ROLLED_BACK = "rolled_back"
    # the file was thrown away before an import ran
    DISCARDED = "discarded"
    EXPIRED = "expired"

    @property
    def busy(self) -> bool:
        """A worker has (or is about to have) the import."""
        return self in (ImportStatus.CHECKING, ImportStatus.QUEUED, ImportStatus.RUNNING)

    @property
    def has_file(self) -> bool:
        return self in (
            ImportStatus.UPLOADED,
            ImportStatus.CHECKING,
            ImportStatus.CHECKED,
            ImportStatus.QUEUED,
            ImportStatus.RUNNING,
        )


BUSY_STATUSES = (ImportStatus.CHECKING, ImportStatus.QUEUED, ImportStatus.RUNNING)


class ImportMode(str, enum.Enum):
    CHECK = "check"
    IMPORT = "import"


class ResponseImportDocument(Record):
    workspace_id: RecordId
    form_id: str
    # who uploaded (the user's id; DELETED_ACTOR once that account was deleted)
    actor_id: str
    status: ImportStatus
    # facts about the upload (no name, no content)
    file_size: int = 0
    encoding: Optional[str] = None
    separator: Optional[str] = None
    row_count: int = 0
    column_count: int = 0
    # the published version of the form the import is checked against
    form_version: Optional[int] = None
    # CSV column position (as text) -> target key (services/response_import/targets.py)
    mapping: Dict[str, str] = {}
    # {"skipInvalidRows": bool}
    options: Dict[str, Any] = {}
    mode: Optional[ImportMode] = None
    # the importer confirmed they may store this data (a run needs it)
    confirmed_at: Optional[dt.datetime] = None
    # outcome
    rows_valid: Optional[int] = None
    rows_invalid: Optional[int] = None
    rows_imported: Optional[int] = None
    rows_skipped: Optional[int] = None
    # at most PROBLEMS_LISTED of {row, column, code}; the totals are exact
    problems: List[Dict[str, Any]] = []
    problem_counts: Dict[str, int] = {}
    problems_truncated: bool = False
    # what the mapping left out and why: [{"column": position, "code": ...}]
    notes: List[Dict[str, Any]] = []
    progress: int = 0
    attempts: int = 0
    started_at: Optional[dt.datetime] = None
    heartbeat_at: Optional[dt.datetime] = None
    checked_at: Optional[dt.datetime] = None
    finished_at: Optional[dt.datetime] = None
    # the uploaded file is deleted by then at the latest
    expires_at: Optional[dt.datetime] = None
    # a response limit or an account deleted meanwhile: a job still running stops
    invalidated_at: Optional[dt.datetime] = None
    # one of our codes, never a message built from content
    error_code: Optional[str] = None
    rolled_back_by: Optional[str] = None
    rolled_back_at: Optional[dt.datetime] = None
    rolled_back_count: Optional[int] = None

    _tz = field_validator(
        "confirmed_at",
        "started_at",
        "heartbeat_at",
        "checked_at",
        "finished_at",
        "expires_at",
        "invalidated_at",
        "rolled_back_at",
    )(_utc)

    class Settings:
        name = "response_imports"


class ResponseImportFileDocument(Record):
    """The uploaded file, encrypted (``data``: base64 of the ciphertext, whose
    context names the workspace, form and import)."""

    import_id: str
    workspace_id: RecordId
    form_id: str
    data: str
    # the file's heading cells, encrypted like ``data`` (never on the import row:
    # a file without a heading row would put a person's data there in clear)
    headers_sealed: Optional[str] = None

    class Settings:
        name = "response_import_files"
