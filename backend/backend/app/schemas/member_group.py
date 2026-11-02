"""Member groups ("Teams" in the product): named sets of a workspace's members
that a form grant can name instead of one person each (form-level access,
``FORM_ACCESS_ENABLED``).

Not the respondent groups (``responder_group``): those admit respondents to a
private form and grant nobody anything in the dashboard.
"""

import unicodedata
from typing import Optional

from common.records import Record, RecordId
from pydantic import model_validator

SOURCE_MANUAL = "manual"
# a team whose members come from a linked directory group (SCIM)
SOURCE_DIRECTORY = "directory"


def name_key(name: str) -> str:
    """What makes two team names the same inside a workspace: compatibility
    forms folded (NFKC: a full-width or ligature spelling is the plain one),
    trimmed, runs of blanks folded, case-insensitive."""
    return " ".join(unicodedata.normalize("NFKC", str(name or "")).split()).casefold()


class MemberGroupDocument(Record):
    """A team of a workspace. ``name_key`` is derived from ``name`` and is the
    unique key (with the workspace) of the table."""

    workspace_id: RecordId
    name: str
    name_key: str = ""
    description: Optional[str] = None
    source: str = SOURCE_MANUAL
    # set only for a directory team
    scim_group_id: Optional[str] = None
    created_by: Optional[str] = None

    @model_validator(mode="after")
    def _derive_key(self):
        self.name_key = name_key(self.name)
        return self

    class Settings:
        name = "member_groups"


class MemberGroupMemberDocument(Record):
    """One member of a manual team. ``id`` is ``derived_id(group_id, user_id)``
    (the same pair always addresses the same row)."""

    group_id: RecordId
    workspace_id: RecordId
    user_id: str

    class Settings:
        name = "member_group_members"
