import datetime as dt
from typing import Optional

from common.records import Record, RecordId


class MCPAuditLogDocument(Record):
    """Every MCP tool call, auditable (plan §2.5): which key did what, when,
    and whether it succeeded. Pairs with the trust story — external AI access
    is visible, not implied."""

    workspace_id: RecordId
    key_id: str
    tool: str
    ok: bool
    detail: Optional[str] = None
    at: dt.datetime

    class Settings:
        name = "mcp_audit_logs"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
        }
