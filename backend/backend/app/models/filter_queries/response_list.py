"""What a staff member can ask of a form's responses list besides a page.

Every filter is on a plaintext column of ``form_responses`` (or on the
status of its deletion request): the answers are encrypted at rest and are
never queried. The values are validated here, so the repository only ever
binds them as parameters.
"""

import datetime as dt
import enum
import hashlib
import json
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Annotated, List, Literal, Optional, Tuple

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field

from backend.app.exceptions import HTTPException

# The sorts the keyset engine serves from an index.
SORT_SUBMITTED = "created_at"
SORT_VERSION = "form_version"
KEYSET_SORTS = (SORT_SUBMITTED, SORT_VERSION)

# The most rows the total counts exactly; above it the list says "10,000+".
COUNT_CAP = 10_000
# A page reached from the start (a link without a cursor) may skip this many rows.
MAX_OFFSET = 10_000
# A cursor reaches pages at most this far from the page it came from.
MAX_CURSOR_PAGES = 10
MAX_PAGE_SIZE = 100


class DeletionStatusFilter(str, enum.Enum):
    """The state of a response's deletion request. ``none``: it has none."""

    NONE = "none"
    PENDING = "pending"
    DECLINED = "declined"
    SUCCESS = "success"


class RespondentFilter(str, enum.Enum):
    ANONYMOUS = "anonymous"
    KNOWN = "known"


class ResponseListFilters(BaseModel):
    """The filters of one list request; all optional, all combined with AND."""

    model_config = ConfigDict(frozen=True)

    # UTC instants (aware): ``submitted_from`` inclusive, ``submitted_to`` exclusive
    submitted_from: Optional[dt.datetime] = None
    submitted_to: Optional[dt.datetime] = None
    status: Tuple[DeletionStatusFilter, ...] = ()
    respondent: Optional[RespondentFilter] = None
    form_version: Tuple[int, ...] = Field(default=(), max_length=50)
    # the responder-email search, as before
    search: Optional[str] = Field(default=None, max_length=320)

    def any(self) -> bool:
        return bool(
            self.submitted_from
            or self.submitted_to
            or self.status
            or self.respondent
            or self.form_version
            or self.search
        )

    def fingerprint(self) -> str:
        """A short hash of the filters, bound into a cursor so it only works
        for the list it was issued for (and carries no filter value)."""

        def instant(value: Optional[dt.datetime]):
            return value.astimezone(dt.timezone.utc).isoformat() if value else None

        canonical = json.dumps(
            [
                instant(self.submitted_from),
                instant(self.submitted_to),
                sorted(s.value for s in self.status),
                self.respondent.value if self.respondent else None,
                sorted(set(self.form_version)),
                self.search or None,
            ],
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


class ResponseListQuery(BaseModel):
    """A validated request for one page of a form's responses."""

    model_config = ConfigDict(frozen=True)

    filters: ResponseListFilters = ResponseListFilters()
    sort_by: str = SORT_SUBMITTED
    descending: bool = True
    page: int = Field(default=1, ge=1)
    size: int = Field(default=25, ge=1, le=MAX_PAGE_SIZE)
    cursor: Optional[str] = Field(default=None, max_length=2048)


@dataclass
class ResponseListOptions:
    """The keyset-only query parameters of the responses list. ``keyset`` is
    true when any of them (or ``paging=keyset``) is present: the list is then
    served from the sort index; without any, the list behaves as before."""

    keyset: bool = False
    filters: dict = field(default_factory=dict)
    cursor: Optional[str] = None


def _aware(name: str, value: Optional[dt.datetime]) -> Optional[dt.datetime]:
    if value is not None and value.tzinfo is None:
        raise HTTPException(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            f"{name} needs a UTC offset, for example 2026-01-31T23:00:00Z.",
        )
    return value


def response_list_options(
    paging: Optional[Literal["keyset"]] = Query(None),
    submitted_from: Optional[dt.datetime] = Query(None, alias="submittedFrom"),
    submitted_to: Optional[dt.datetime] = Query(None, alias="submittedTo"),
    status: List[DeletionStatusFilter] = Query([], max_length=4),
    respondent: Optional[RespondentFilter] = Query(None),
    form_version: List[Annotated[int, Field(ge=0, le=1_000_000)]] = Query(
        [], alias="formVersion", max_length=50
    ),
    cursor: Optional[str] = Query(None, max_length=2048),
) -> ResponseListOptions:
    submitted_from = _aware("submittedFrom", submitted_from)
    submitted_to = _aware("submittedTo", submitted_to)
    if submitted_from and submitted_to and submitted_from >= submitted_to:
        raise HTTPException(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "submittedFrom must be before submittedTo.",
        )
    filters = {
        "submitted_from": submitted_from,
        "submitted_to": submitted_to,
        "status": tuple(dict.fromkeys(status)),
        "respondent": respondent,
        "form_version": tuple(dict.fromkeys(form_version)),
    }
    return ResponseListOptions(
        keyset=bool(paging or cursor or any(filters.values())),
        filters=filters,
        cursor=cursor,
    )
