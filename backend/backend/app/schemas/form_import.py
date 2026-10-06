import datetime as dt
from typing import Any, Dict, List, Optional

from beanie import PydanticObjectId
from pydantic import BaseModel

from backend.app.handlers.database import entity
from common.configs.mongo_document import MongoDocument


class ImportStatus:
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

    ACTIVE = (QUEUED, RUNNING)


# error code and message of an import that stopped making progress (its
# process was killed, e.g. by a deploy) and was expired so it no longer holds
# the workspace's import slot (#703)
CODE_INTERRUPTED = "interrupted"
MESSAGE_INTERRUPTED = "The import was interrupted. Please try again."


def _utc(value: Optional[dt.datetime]) -> Optional[dt.datetime]:
    """Stored dates may come back naive (Mongo): they are UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value


class PageAnalysis(BaseModel):
    """What the page analysis found on one page and how the page will be read."""

    number: int
    width: float
    height: float
    route: str  # widgets | text | vision | scan
    reasons: List[str] = []
    chars: int = 0
    widgets: int = 0
    images: int = 0
    image_coverage: float = 0.0
    vector_objects: int = 0
    fonts: List[str] = []
    legacy_fonts: List[str] = []


@entity
class FormImportDocument(MongoDocument):
    """One import of an uploaded PDF or image into a draft form.

    Created with the draft form, so the uploaded original lives in the form's
    private storage folder and is deleted with the form. ``stages`` holds each
    finished stage's checkpoint, so a retried job resumes instead of redoing
    work. Nothing a respondent may have written on the uploaded document is
    ever stored here: only structure.
    """

    workspace_id: PydanticObjectId
    # None once a failed import has removed its empty draft (see report notes)
    form_id: Optional[str] = None
    created_by: str
    status: str = ImportStatus.QUEUED
    stage: Optional[str] = None
    error: Optional[str] = None
    # stable reason for ``error`` (the screens translate it): a refusal code
    # (encrypted, too_many_pages, unreadable, timeout, no_questions, ...),
    # "unavailable", "failed", "interrupted" (no progress for too long: its
    # process died), or "waiting_for_reader" while queued for a retry
    error_code: Optional[str] = None
    file_name: str
    content_type: str
    size_bytes: int
    sha256: str
    source_key: str
    page_count: Optional[int] = None
    pages: List[PageAnalysis] = []
    stages: Dict[str, Any] = {}
    report: Dict[str, Any] = {}
    started_at: Optional[dt.datetime] = None
    finished_at: Optional[dt.datetime] = None
    # the uploading user's explicit consent to send this document's page text
    # and images to the AI provider; without it only the built-in reader runs
    ai_consent: bool = False
    ai_consent_at: Optional[dt.datetime] = None
    ai_consent_by: Optional[str] = None
    # bumped while the import's job is alive (every save of the pipeline and a
    # heartbeat during long stages and retry waits): an active import whose
    # last progress is older than PDF_IMPORT_STALE_AFTER_S was interrupted
    heartbeat_at: Optional[dt.datetime] = None

    def last_progress(self) -> Optional[dt.datetime]:
        """The latest sign of life: the heartbeat, or for records written
        before heartbeats existed, when the import started or was created.
        (Not ``updated_at``: only the Mongo store bumps it on save.)"""
        seen = [
            _utc(v)
            for v in (self.heartbeat_at, self.started_at, self.created_at)
            if v is not None
        ]
        return max(seen) if seen else None

    def is_stale(self, stale_before: dt.datetime) -> bool:
        """Still marked active but without any progress since ``stale_before``."""
        if self.status not in ImportStatus.ACTIVE:
            return False
        last = self.last_progress()
        return last is None or last < stale_before

    def mark_interrupted(self, now: dt.datetime) -> None:
        self.status = ImportStatus.FAILED
        self.error = MESSAGE_INTERRUPTED
        self.error_code = CODE_INTERRUPTED
        self.report["refused"] = CODE_INTERRUPTED
        self.finished_at = now

    class Settings:
        # native dates (no ISO-string encoders): the limits query compares them
        name = "form_imports"
