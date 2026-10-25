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

    class Settings:
        name = "workspace_api_keys"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
        }
