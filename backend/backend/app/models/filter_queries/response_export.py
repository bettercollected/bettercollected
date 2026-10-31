"""Which responses of a form an export holds, besides "all of them".

The filters are those of the responses list (:class:`ResponseListFilters`:
``submittedFrom``, ``submittedTo``, ``status``, ``respondent``, ``formVersion``
and the responder-email search), validated by the same model and turned into the
same SQL by the repository (``_list_filters``), so the export of a filtered list
is that filter. Every one is on a plaintext column of ``form_responses`` or on the
status of its deletion request: the answers are encrypted at rest and never queried.
"""

import datetime as dt

from backend.app.models.filter_queries.response_list import (  # noqa: F401
    DeletionStatusFilter,
    RespondentFilter,
    ResponseListFilters,
)


def _utc(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc)


class ResponseExportFilters(ResponseListFilters):
    def audit_summary(self) -> dict:
        """What the audit entry keeps: the filters, with the search reduced to
        the fact that there was one (it is a respondent's email address)."""
        summary: dict = {}
        if self.submitted_from:
            summary["submitted_from"] = _utc(self.submitted_from).isoformat()
        if self.submitted_to:
            summary["submitted_to"] = _utc(self.submitted_to).isoformat()
        if self.status:
            summary["status"] = sorted(s.value for s in self.status)
        if self.respondent:
            summary["respondent"] = self.respondent.value
        if self.form_version:
            summary["form_version"] = sorted(set(self.form_version))
        if self.search:
            summary["search"] = True
        return summary
