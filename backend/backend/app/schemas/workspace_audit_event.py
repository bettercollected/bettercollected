from typing import Optional

from common.records import Record, RecordId

# an owner's email-code session was let into an SSO-required workspace (first
# request of the session)
SSO_BREAK_GLASS_SESSION = "sso_break_glass_session"
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

    class Settings:
        name = "workspace_audit_events"
