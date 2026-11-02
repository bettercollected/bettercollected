"""What the audit log routes answer (services/audit_log). Codes and ids, never
prose: the dashboard words every entry in the viewer's language from ``event``
and the fields. No answer, no address, no title typed into a form field, and
nothing outside these classes is ever copied from a stored entry."""

import datetime as dt
from typing import Dict, List, Optional

from fastapi_camelcase import CamelModel


class AuditEntryDto(CamelModel):
    id: str
    # a code of the catalogue (services/audit_log/catalog.py); an older
    # dashboard shows a neutral sentence for one it does not know
    event: str
    area: str
    at: dt.datetime
    # who did it: a user id (see ``labels.members``); None for an entry whose
    # actor was not recorded
    actor_id: Optional[str] = None
    # the login session, only for an Owner or an Admin
    session_id: Optional[str] = None
    # who it was done to / who a form was handed to
    target_user_id: Optional[str] = None
    to_user_id: Optional[str] = None
    form_id: Optional[str] = None
    # a response id only for someone who may read that form's responses
    response_id: Optional[str] = None
    revision: Optional[int] = None
    group_id: Optional[str] = None
    # a grant's role (Editor, Reviewer, Viewer), whether it may export, and a
    # form's new access mode
    grant_role: Optional[str] = None
    grant_export: Optional[bool] = None
    access_mode: Optional[str] = None
    # TEAM_LINKED: a directory group was linked to the team (``group_id``) or
    # unlinked from it
    linked: Optional[bool] = None
    # TEAM_LINKED: our id of the directory group (an id only; the directory's
    # own name for it is not shown)
    scim_group_id: Optional[str] = None
    # a member's role and the one it replaced (workspace role codes)
    role: Optional[str] = None
    previous_role: Optional[str] = None
    # how many rows, grants, responses or entries the action touched
    count: Optional[int] = None
    # TOTP_POLICY_CHANGED: whether an authenticator app is required now
    required: Optional[bool] = None
    export_channel: Optional[str] = None
    export_format: Optional[str] = None
    # API key events: the key's id (never its name or token), the reason it
    # was revoked, its role (and the one before), its form scope and whether
    # the change gave it more access
    key_id: Optional[str] = None
    reason: Optional[str] = None
    key_role: Optional[str] = None
    key_role_before: Optional[str] = None
    form_scope: Optional[str] = None
    widened: Optional[bool] = None
    # settings entries: the kind of single sign-on connection or directory
    # (``saml`` / ``oidc``, the directory's type), an on/off setting's new
    # value and the AI provider's id; never a name, a hostname or a URL
    connection_type: Optional[str] = None
    directory_type: Optional[str] = None
    enabled: Optional[bool] = None
    provider: Optional[str] = None
    # AUDIT_RETENTION_CHANGED: the retention now and the one it replaced, in months
    retention_months: Optional[int] = None
    previous_retention_months: Optional[int] = None
    # integration entries: which parts of the configuration changed (names
    # from a fixed list, never their content)
    changed: Optional[List[str]] = None
    # request entries (break-glass): the method and the route's template
    method: Optional[str] = None
    path: Optional[str] = None


class MemberLabelDto(CamelModel):
    """``status``: ``member`` (a current member of this workspace; ``name`` is
    their display name, empty when the lookup was unavailable) or ``former``
    (no longer a member: no name, the dashboard says "a member who has left")."""

    status: str
    name: Optional[str] = None


class FormLabelDto(CamelModel):
    """``status``: ``available`` (a form of this workspace; ``title`` is its
    current title) or ``gone`` (deleted, or not this workspace's)."""

    status: str
    title: Optional[str] = None


class TeamLabelDto(CamelModel):
    """``status``: ``available`` (``name`` is the team's current name) or
    ``gone`` (deleted: the dashboard says "a deleted team")."""

    status: str
    name: Optional[str] = None


class AuditLabelsDto(CamelModel):
    """The ids of this page, resolved now and within this workspace only."""

    members: Dict[str, MemberLabelDto] = {}
    forms: Dict[str, FormLabelDto] = {}
    teams: Dict[str, TeamLabelDto] = {}


class AuditPageDto(CamelModel):
    entries: List[AuditEntryDto]
    # opaque; send it back as ``cursor`` for the next (older) page; None at the end
    next_cursor: Optional[str] = None
    labels: AuditLabelsDto
    # how many days an entry is kept (the page states it)
    retention_days: int


class AuditRetentionDto(CamelModel):
    """How long this workspace's audit entries are kept."""

    # the setting, in whole months, and what it comes to in days
    months: int
    days: int
    # the choices, shortest first; none is shorter than ``minimum_months``
    options: List[int]
    minimum_months: int
    default_months: int
    # only an owner changes it
    can_change: bool
    # set by a change that shortened the period: entries older than the new
    # period are deleted by the next daily clean-up, not at once
    applies_at_next_purge: bool = False


class SetAuditRetentionDto(CamelModel):
    months: int
