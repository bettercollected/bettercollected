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
    # TOTP_* entries made by someone else (an owner or the platform admin
    # resetting a member's factor): the account it was done to
    target_user_id: Optional[str] = None

    class Settings:
        name = "workspace_audit_events"
