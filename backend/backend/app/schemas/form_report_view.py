"""A saved view of a form's report (``REPORTING_ENABLED``, docs/reporting.md):
a name, a scope and a validated report definition, nothing else.

``scope`` is ``private`` (the owner's notebook: not even an owner or an admin of
the workspace reads it) or ``form`` (everyone who may open the form's report).
``definition`` is the report definition of ``services/reporting/definition.py``
as validated when the view was written: question and option ids, numbers, dates
and enums, never an answer, an identity or a respondent's text. ``revision``
counts the changes, so a change made from a stale copy is refused.
"""

from typing import Any, Dict

from common.records import Record, RecordId

SCOPE_PRIVATE = "private"
SCOPE_FORM = "form"
SCOPES = (SCOPE_PRIVATE, SCOPE_FORM)


class FormReportViewDocument(Record):
    workspace_id: RecordId
    form_id: str
    owner_id: str
    scope: str = SCOPE_PRIVATE
    name: str
    definition: Dict[str, Any]
    revision: int = 1

    class Settings:
        name = "form_report_views"
