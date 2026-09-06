from backend.app.schemas.mcp_audit_log import MCPAuditLogDocument
from common.db.routing import write_op


class McpAuditLogRepository:
    @write_op(replay=True)
    async def add(self, **fields) -> MCPAuditLogDocument:
        return await MCPAuditLogDocument(**fields).save()
