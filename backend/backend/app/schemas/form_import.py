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

    class Settings:
        # native dates (no ISO-string encoders): the limits query compares them
        name = "form_imports"
