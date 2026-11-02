import datetime as dt
from typing import Any, Dict, List, Optional

from fastapi_camelcase import CamelModel
from pydantic import Field


class StaffAnswersPatch(CamelModel):
    """The answers a staff member changes, by question id; the others stay.
    Each is an answer as a respondent's submission carries it."""

    answers: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class StaffAnswersResult(CamelModel):
    # the questions whose answer really changed (a no-op edit has none)
    changed: List[str]
    # the number of the history entry the edit wrote, none when nothing changed
    revision: Optional[int] = None


class RevisionActorDto(CamelModel):
    """Who edited: ``respondent`` (the person who answered), ``api_key`` (a
    workspace API key editing a response it made; nothing else is shown), or
    ``staff`` with the member's current name and the role they held. ``former`` says the
    member is gone (an id never leaves)."""

    kind: str
    name: Optional[str] = None
    role: Optional[str] = None
    former: bool = False


class RevisionChangedDto(CamelModel):
    id: str
    # the question's title in the version the response was given in
    title: Optional[str] = None


class RevisionEntryDto(CamelModel):
    seq: int
    at: Optional[dt.datetime] = None
    actor: RevisionActorDto
    changed: List[RevisionChangedDto]


class RevisionListDto(CamelModel):
    revisions: List[RevisionEntryDto]


class RevisionValuesDto(CamelModel):
    """One entry's previous values, unsealed: the answer each changed question
    had before (null: it had none). Never carries a link to a file."""

    seq: int
    values: Dict[str, Optional[Dict[str, Any]]]
