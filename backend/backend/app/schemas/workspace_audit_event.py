from typing import Optional

from common.records import Record, RecordId

# a request by an owner's email-code session that the SSO requirement would
# otherwise have refused: one entry per request
SSO_BREAK_GLASS_REQUEST = "sso_break_glass_request"
# an owner signed in with an email code on an address the workspace requires
# single sign-on for (the session may never reach a workspace route)
SSO_BREAK_GLASS_SIGN_IN = "sso_break_glass_sign_in"


# a staff member changed answers of a response (docs/response-revisions.md):
# who, when, the form and response and the history entry's number, no value
RESPONSE_STAFF_EDIT = "response_staff_edit"
# a staff member opened the previous values of one history entry
RESPONSE_REVISION_READ = "response_revision_read"

# second-factor (authenticator app) events of an account (docs/totp.md): ids
# only, never a code, a secret or an address. ``workspace_id`` is NO_WORKSPACE
# when no workspace is involved.
TOTP_ENROLLED = "totp_enrolled"
TOTP_REMOVED = "totp_removed"
TOTP_RESET = "totp_reset"
TOTP_RECOVERY_USED = "totp_recovery_used"
TOTP_RECOVERY_REGENERATED = "totp_recovery_regenerated"
TOTP_LOCKED = "totp_locked"
TOTP_POLICY_CHANGED = "totp_policy_changed"
TOTP_EVENTS = (
    TOTP_ENROLLED,
    TOTP_REMOVED,
    TOTP_RESET,
    TOTP_RECOVERY_USED,
    TOTP_RECOVERY_REGENERATED,
    TOTP_LOCKED,
    TOTP_POLICY_CHANGED,
)
# form-level access events (``FORM_ACCESS_ENABLED``): grants, teams and a
# form's access mode. Ids and enum values only, never a team name, a form title
# or an address.
ACCESS_GRANT_ADDED = "access_grant_added"
ACCESS_GRANT_CHANGED = "access_grant_changed"
ACCESS_GRANT_REMOVED = "access_grant_removed"
ACCESS_MODE_CHANGED = "access_mode_changed"
TEAM_CREATED = "team_created"
TEAM_RENAMED = "team_renamed"
TEAM_DELETED = "team_deleted"
TEAM_MEMBER_ADDED = "team_member_added"
TEAM_MEMBER_REMOVED = "team_member_removed"
# a directory group linked to or unlinked from a team
TEAM_LINKED = "team_linked"
# removing a member deleted N grants and team memberships
ACCESS_MEMBER_PURGED = "access_member_purged"
# removing a member handed a form they created to the workspace's billing owner
# (form_id, target_user_id = who it was, to_user_id = who it is now)
FORM_CREATOR_REASSIGNED = "form_creator_reassigned"
ACCESS_EVENTS = (
    ACCESS_GRANT_ADDED,
    ACCESS_GRANT_CHANGED,
    ACCESS_GRANT_REMOVED,
    ACCESS_MODE_CHANGED,
    TEAM_CREATED,
    TEAM_RENAMED,
    TEAM_DELETED,
    TEAM_MEMBER_ADDED,
    TEAM_MEMBER_REMOVED,
    TEAM_LINKED,
    ACCESS_MEMBER_PURGED,
    FORM_CREATOR_REASSIGNED,
)
# workspace members (members.manage): ids and enum values only, never an
# address. An invitation has no account yet, so it is named by its id.
MEMBER_INVITED = "member_invited"
MEMBER_INVITATION_REVOKED = "member_invitation_revoked"
MEMBER_INVITATION_ACCEPTED = "member_invitation_accepted"
MEMBER_REMOVED = "member_removed"
MEMBER_ROLE_CHANGED = "member_role_changed"
# forms and responses: the form, how many responses, never a title or an answer
FORM_PUBLISHED = "form_published"
FORM_DELETED = "form_deleted"
RESPONSES_DELETED = "responses_deleted"
# data left through an export, a bulk read or a response PDF: a pointer to the
# export's own audit row (``export_id``), with its channel, format and rows
RESPONSE_EXPORT = "response_export"
MEMBER_FORM_EVENTS = (
    MEMBER_INVITED,
    MEMBER_INVITATION_REVOKED,
    MEMBER_INVITATION_ACCEPTED,
    MEMBER_REMOVED,
    MEMBER_ROLE_CHANGED,
    FORM_PUBLISHED,
    FORM_DELETED,
    RESPONSES_DELETED,
    RESPONSE_EXPORT,
)
# the reserved workspace id of an event that belongs to no workspace
NO_WORKSPACE = "000000000000000000000000"

# the events of the single sign-on break-glass log (what its page lists)
SSO_EVENTS = (SSO_BREAK_GLASS_REQUEST, SSO_BREAK_GLASS_SIGN_IN)


class WorkspaceAuditEventDocument(Record):
    """A security event of a workspace (docs/sso.md, "Owner break-glass is
    audited"): ids only, never an address or a name. The time is
    ``created_at``."""

    workspace_id: RecordId
    user_id: str
    session_id: Optional[str] = None
    event: str
    # request entries: the HTTP method and the route's path *template*
    # (``/workspaces/{workspace_id}/forms``), never a query, a body or a
    # concrete id from the path
    method: Optional[str] = None
    path: Optional[str] = None
    # response entries (RESPONSE_*): ids and the history entry's number only
    form_id: Optional[str] = None
    response_id: Optional[str] = None
    revision: Optional[int] = None
    # TOTP_POLICY_CHANGED: what the workspace rule was set to
    required: Optional[bool] = None
    # TOTP_* entries made by someone else (an owner or the platform admin
    # resetting a member's factor): the account it was done to
    target_user_id: Optional[str] = None
    # FORM_CREATOR_REASSIGNED: the person the form was handed to
    to_user_id: Optional[str] = None
    # ACCESS_* / TEAM_* entries (form-level access): the team, the role and
    # export flag of a grant, a form's new access mode, a number of rows
    group_id: Optional[str] = None
    grant_role: Optional[str] = None
    grant_export: Optional[bool] = None
    access_mode: Optional[str] = None
    count: Optional[int] = None
    # MEMBER_*: the invitation, the role it gives or the member now holds (an
    # enum value of WorkspaceRoles) and, for a change, the one it replaced
    invitation_id: Optional[str] = None
    role: Optional[str] = None
    previous_role: Optional[str] = None
    # RESPONSE_EXPORT: the id of the export's row (``response_exports``), its
    # channel and format (enum values); the number of rows is ``count``
    export_id: Optional[str] = None
    export_channel: Optional[str] = None
    export_format: Optional[str] = None

    class Settings:
        name = "workspace_audit_events"
