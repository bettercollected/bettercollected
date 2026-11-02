"""A workspace's reusable section (``services/reusable_sections``): a name, the
questions (and layout containers) of the section as a form spec fragment, a
version, and the versions before it. Content the workspace's editors wrote; no
answer and no personal data of respondents."""

import datetime as dt
from typing import Any, Dict, List, Optional

from common.records import Record, RecordId
from pydantic import BaseModel, Field


class SectionVersion(BaseModel):
    """One earlier version of a section, kept so a copy can be diffed against
    the version it was made from."""

    version: int = Field(..., ge=1)
    saved_at: Optional[dt.datetime] = None
    saved_by: Optional[str] = None
    name: str = ""
    fields: List[Dict[str, Any]] = []
    containers: List[Dict[str, Any]] = []


class ReusableSectionDocument(Record):
    workspace_id: RecordId
    name: str
    # the folded name: a name is unique per workspace (revision 0034)
    name_key: str
    description: Optional[str] = None
    # the current version; the content below is that version's
    version: int = 1
    # the questions and containers in the form spec's shape (camelCase)
    fields: List[Dict[str, Any]] = []
    containers: List[Dict[str, Any]] = []
    question_count: int = 0
    # earlier versions, newest first (at most limits.VERSIONS_KEPT - 1)
    history: List[SectionVersion] = []
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    class Settings:
        name = "workspace_library_sections"
