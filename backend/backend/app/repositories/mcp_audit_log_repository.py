from backend.app.schemas.mcp_audit_log import MCPAuditLogDocument


class McpAuditLogRepository:
    async def add(self, **fields) -> MCPAuditLogDocument:
        return await MCPAuditLogDocument(**fields).save()
