"""Stored records of the responses export (``services/response_export``): one
row per export, which is also its audit entry, and the chunks of a background
job's file.

The export row never holds an answer: who asked, when, for which form, how many
rows, which columns and which filters (the search text only as "a search was
used"), the state of the job and when its file goes. The job's own parameters
(the real filters) sit sealed in ``params_sealed`` until the job ends. A file is
stored only for a job, only as encrypted chunks, and goes 24 hours after it was
built, when its requester deletes it, or when responses of the form are deleted.
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


class ExportKind(str, enum.Enum):
    STREAM = "stream"
    JOB = "job"


class ExportStatus(str, enum.Enum):
    # a streamed export: in flight, then finished
    STREAMING = "streaming"
    COMPLETED = "completed"
    # a job: waiting, building, built
    QUEUED = "queued"
    RUNNING = "running"
    READY = "ready"
    # a job's file is gone: past its 24 hours, deleted by its requester, or
    # responses of the form were deleted after it was built
    EXPIRED = "expired"
    DISCARDED = "discarded"
    ERASED = "erased"
    FAILED = "failed"
    # stopped before it was built: responses were deleted meanwhile, or the
    # requester no longer holds the permission
    CANCELLED = "cancelled"

    @property
    def unfinished(self) -> bool:
        return self in (ExportStatus.QUEUED, ExportStatus.RUNNING)


class ResponseExportDocument(Record):
    workspace_id: RecordId
    form_id: str
    # who asked (the user's id; DELETED_ACTOR once that account was deleted)
    actor_id: str
    # how the data left: "export" (the export control, POST .../exports) or
    # "all_submissions" (the bulk JSON route, audited the same way), or "api_key" /
    # "mcp" (a workspace API key's reads of responses; ``actor_id`` is ``api-key:<key id>``)
    channel: str = "export"
    kind: ExportKind
    status: ExportStatus
    # "csv", or "zip" when the form's repeating groups export as tables
    format: str = "csv"
    # the keys of the columns exported (see services/response_export/table.py)
    columns: List[str] = []
    # the filters, as recorded in the audit entry: never the search text
    filters: Dict[str, Any] = {}
    # a job's real parameters (filters with the search text), sealed; removed
    # when the job ends
    params_sealed: Optional[str] = None
    # matching rows when it was asked for, and rows written
    expected_rows: Optional[int] = None
    row_count: Optional[int] = None
    # claims of the job so far; a run owns the export only while this is still
    # the value it claimed (a swept and re-run job makes the old run stop)
    attempts: int = 0
    # when the job was claimed (by its latest claim)
    started_at: Optional[dt.datetime] = None
    # while it builds, when the running job last showed it is alive (a stored chunk
    # or a read batch); the sweep tells a stuck job by this, never by ``started_at``.
    # Kept in the document: no column, no migration (rows from before have none and
    # fall back to ``started_at``)
    heartbeat_at: Optional[dt.datetime] = None
    finished_at: Optional[dt.datetime] = None
    # file: name offered to the user, size, and when it is deleted at the latest
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    chunk_count: Optional[int] = None
    expires_at: Optional[dt.datetime] = None
    # the last complete download and how many there were (the file stays
    # until it expires: any number of downloads)
    downloaded_at: Optional[dt.datetime] = None
    download_count: int = 0
    file_deleted_at: Optional[dt.datetime] = None
    # set when responses of the form were deleted: a job still building then
    # throws its file away instead of keeping it
    invalidated_at: Optional[dt.datetime] = None
    # one of our codes, never a message built from content
    error_code: Optional[str] = None

    _tz = field_validator(
        "started_at",
        "heartbeat_at",
        "finished_at",
        "expires_at",
        "downloaded_at",
        "file_deleted_at",
        "invalidated_at",
    )(_utc)

    class Settings:
        name = "response_exports"


class ResponseExportChunkDocument(Record):
    """One encrypted piece of a job's file (``data``: base64 of the ciphertext,
    whose context names the export, the piece and the requester)."""

    export_id: str
    workspace_id: RecordId
    form_id: str
    index: int
    data: str
    # the claim of the run that wrote it (a chunk of another claim is not the file)
    attempt: int = 0

    class Settings:
        name = "response_export_chunks"
