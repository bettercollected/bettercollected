"""Which responses of a form an export holds, besides "all of them".

The names are those of the responses list's filters (``submittedFrom``,
``submittedTo``, ``respondent``, ``formVersion``, and the responder-email search),
so the export of a filtered list is the same filter. Every one is on a
plaintext column of ``form_responses``: the answers are encrypted at rest and
are never queried. The values are validated here, so the repository only ever
binds them as parameters.

TODO: when the list's filter model (``ResponseListFilters``, keyset list branch)
is on develop, reuse it here instead of this copy, and add its deletion-request
``status`` filter.
"""

import datetime as dt
import enum
from typing import Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field


class RespondentFilter(str, enum.Enum):
    ANONYMOUS = "anonymous"
    KNOWN = "known"


class ResponseExportFilters(BaseModel):
    """All optional, combined with AND."""

    model_config = ConfigDict(frozen=True)

    # UTC instants (aware): ``submitted_from`` inclusive, ``submitted_to`` exclusive
    submitted_from: Optional[dt.datetime] = None
    submitted_to: Optional[dt.datetime] = None
    respondent: Optional[RespondentFilter] = None
    form_version: Tuple[int, ...] = Field(default=(), max_length=50)
    # the responder-email search of the list
    search: Optional[str] = Field(default=None, max_length=320)

    def any(self) -> bool:
        return bool(
            self.submitted_from
            or self.submitted_to
            or self.respondent
            or self.form_version
            or self.search
        )

    def audit_summary(self) -> dict:
        """What the audit entry keeps: the filters, with the search reduced to
        the fact that there was one (it is a respondent's email address)."""
        summary: dict = {}
        if self.submitted_from:
            summary["submitted_from"] = _utc(self.submitted_from).isoformat()
        if self.submitted_to:
            summary["submitted_to"] = _utc(self.submitted_to).isoformat()
        if self.respondent:
            summary["respondent"] = self.respondent.value
        if self.form_version:
            summary["form_version"] = sorted(set(self.form_version))
        if self.search:
            summary["search"] = True
        return summary


def _utc(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc)
