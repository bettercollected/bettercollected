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
# API key lifecycle events: ids and enum values only, never a key's name, prefix
# or token, nor a form title.
# an API key was revoked (key_id, reason): because its creator left (removed
# from the workspace, their account deleted or the directory deprovisioned them;
# target_user_id = the creator), or by an admin
API_KEY_REVOKED = "api_key_revoked"
# API_KEY_ROLES_ENABLED: a key created, its role or form scope changed, a form
# added to or removed from its list
API_KEY_CREATED = "api_key_created"
API_KEY_ROLE_CHANGED = "api_key_role_changed"
API_KEY_SCOPE_CHANGED = "api_key_scope_changed"
API_KEY_FORM_ADDED = "api_key_form_added"
API_KEY_FORM_REMOVED = "api_key_form_removed"
API_KEY_EVENTS = (
    API_KEY_REVOKED,
    API_KEY_CREATED,
    API_KEY_ROLE_CHANGED,
    API_KEY_SCOPE_CHANGED,
    API_KEY_FORM_ADDED,
    API_KEY_FORM_REMOVED,
)
# the reasons of API_KEY_REVOKED
REVOKED_MEMBER_REMOVED = "member_removed"
REVOKED_ACCOUNT_DELETED = "account_deleted"
REVOKED_SCIM_DEPROVISIONED = "scim_deprovisioned"
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
    # API_KEY_* entries: the key (its id only), why it was revoked, its role (and
    # the one before), its form scope and whether the change gave the key more
    # access
    key_id: Optional[str] = None
    reason: Optional[str] = None
    key_role: Optional[str] = None
    key_role_before: Optional[str] = None
    form_scope: Optional[str] = None
    widened: Optional[bool] = None

    class Settings:
        name = "workspace_audit_events"
