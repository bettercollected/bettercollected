"""A grant on one form (``FORM_ACCESS_ENABLED``): a role on that form for a
person or a team, on top of (or, on a restricted form, instead of) their
workspace role (docs/enterprise-access-model.md, "Form-level scope").

``subject_type`` is free text on purpose: ``user`` and ``group`` (a member
group) today; API keys reuse the table with ``key``.
"""

from typing import Optional

from common.records import Record, RecordId

SUBJECT_USER = "user"
SUBJECT_GROUP = "group"

ROLE_EDITOR = "EDITOR"
ROLE_REVIEWER = "REVIEWER"
ROLE_VIEWER = "VIEWER"
GRANT_ROLES = (ROLE_EDITOR, ROLE_REVIEWER, ROLE_VIEWER)


class FormAccessGrantDocument(Record):
    workspace_id: RecordId
    form_id: str
    subject_type: str
    subject_id: str
    # a role this code does not know grants nothing (a newer release's)
    role: str
    # may export responses: Reviewer and Viewer grants only; an Editor grant
    # exports anyway. Only owners and admins set it.
    export: bool = False
    created_by: Optional[str] = None

    class Settings:
        name = "form_access_grants"
