from typing import List

from beanie import PydanticObjectId

from backend.app.schemas.mcp_audit_log import MCPAuditLogDocument
from common.db.routing import write_op


class McpAuditLogRepository:
    @write_op(replay=True)
    async def add(self, **fields) -> MCPAuditLogDocument:
        return await MCPAuditLogDocument(**fields).save()

    async def list_by_workspace(
        self, workspace_id: PydanticObjectId
    ) -> List[MCPAuditLogDocument]:
        return await MCPAuditLogDocument.find({"workspace_id": workspace_id}).to_list()
