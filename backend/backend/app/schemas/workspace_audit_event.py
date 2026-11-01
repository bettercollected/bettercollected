from typing import Optional

from common.records import Record, RecordId

# a request by an owner's email-code session that the SSO requirement would
# otherwise have refused: one entry per request
SSO_BREAK_GLASS_REQUEST = "sso_break_glass_request"
# an owner signed in with an email code on an address the workspace requires
# single sign-on for (the session may never reach a workspace route)
SSO_BREAK_GLASS_SIGN_IN = "sso_break_glass_sign_in"


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

    class Settings:
        name = "workspace_audit_events"
