import datetime as dt
from typing import List, Optional

from common.records import Record, RecordId


class WorkspaceAPIKeyDocument(Record):
    """A workspace-scoped API key (plan §2.5) — the credential MCP and the
    public API authenticate with.

    Only the SHA-256 of the token is stored; the full token is shown exactly
    once at creation. ``prefix`` (the first characters) is kept for display so
    a key can be recognized without being recoverable. Scopes gate what the
    key may do; ``created_by`` is the acting user for authorization checks.
    """

    workspace_id: RecordId
    name: str
    key_hash: str  # unique
    prefix: str
    scopes: List[str] = []
    created_by: str
    revoked: bool = False
    # A key with responses:read gives an external AI client full, unredacted
    # answers; the admin who created it acknowledged that (#715).
    responses_read_acknowledged_by: Optional[str] = None
    responses_read_acknowledged_at: Optional[dt.datetime] = None
    last_used_at: Optional[dt.datetime] = None
    # With submissions:write: the forms the key may submit to (None = every
    # form of the workspace).
    submission_form_ids: Optional[List[str]] = None
    # What the key may do at most (API_KEY_ROLES_ENABLED; docs/enterprise-
    # access-model.md, section 4): None = "as its creator" (every key made
    # before roles existed, and every key made without one); otherwise EDITOR,
    # REVIEWER, VIEWER or PRIVACY_OFFICER. It never adds to the creator: a
    # key's permissions are the creator's current ones narrowed by this. An
    # unknown value (a newer release's) gives the key nothing.
    role: Optional[str] = None
    # "all" (every form the creator and role reach) or "listed" (only forms
    # with a grant row for this key). Stored on the key, never inferred from
    # "has rows": deleting the last row must narrow a key to nothing, not widen
    # it. An unknown value is read as "listed".
    #
    # Rolling back: a release that does not know these two fields drops them
    # the next time it saves the key (its first authenticated call), and the key
    # is then unlimited. Revoke the keys that carry them before rolling back.
    form_scope: str = "all"

    class Settings:
        name = "workspace_api_keys"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
        }
