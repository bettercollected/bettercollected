"""Respondent feedback payloads: what staff post, what staff see (with who
posted each update) and what the respondent sees (no staff identity)."""

import datetime as dt
from typing import List, Optional

from fastapi_camelcase import CamelModel
from pydantic import Field, model_validator

# One update is a short note to one person, not a document.
MAX_FEEDBACK_MESSAGE_LENGTH = 5000


class RespondentFeedbackPost(CamelModel):
    """A new update on a submission: a status from the form's list and/or a
    message; at least one of the two."""

    status: Optional[str] = Field(None, max_length=200)
    message: Optional[str] = Field(None, max_length=MAX_FEEDBACK_MESSAGE_LENGTH)

    @model_validator(mode="after")
    def _status_or_message(self):
        self.status = (self.status or "").strip() or None
        self.message = (self.message or "").strip() or None
        if self.status is None and self.message is None:
            raise ValueError("Give a status, a message or both.")
        return self


class StaffFeedbackEntry(CamelModel):
    id: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None
    created_at: Optional[dt.datetime] = None
    created_by: Optional[str] = None
    created_by_email: Optional[str] = None


class StaffFeedback(CamelModel):
    """The feedback panel of a submission, for workspace members."""

    entries: List[StaffFeedbackEntry] = Field(default_factory=list)
    current_status: Optional[str] = None
    # Whether this user may post (workspace admins and the owner).
    can_post: bool = False
    # Whether a new update emails the respondent (verified identity on and an
    # identified submitter); otherwise they only see it with the submission
    # number or when signed in.
    notifies_respondent: bool = False


class RespondentFeedbackEntry(CamelModel):
    status: Optional[str] = None
    message: Optional[str] = None
    created_at: Optional[dt.datetime] = None


class RespondentFeedbackView(CamelModel):
    """What the respondent sees: the organisation as the author, never the
    staff member who posted."""

    author: Optional[str] = None
    current_status: Optional[str] = None
    updated_at: Optional[dt.datetime] = None
    # Left out in listings, which only show the current status.
    entries: Optional[List[RespondentFeedbackEntry]] = None
