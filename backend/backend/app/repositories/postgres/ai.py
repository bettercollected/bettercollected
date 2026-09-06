"""Postgres twins of the ai- and analytics-group repositories."""

from typing import List, Optional

from beanie import PydanticObjectId

from backend.app.repositories.postgres.forms import _oid
from backend.app.schemas.ai_preference_memory import UserAIPreferenceMemoryDocument
from backend.app.schemas.flow_event import FlowEventDocument
from backend.app.schemas.form_ai_insight import FormAIInsightDocument
from backend.app.schemas.form_ai_session import FormAISessionDocument
from backend.app.schemas.mcp_audit_log import MCPAuditLogDocument
from backend.app.schemas.workspace_ai_profile import WorkspaceAIProfileDocument
from backend.db.models import (
    AiPreferenceMemoryRow,
    FormAiInsightRow,
    FormAiSessionRow,
    FormFlowEventRow,
    McpAuditLogRow,
    WorkspaceAiProfileRow,
)
from common.db import PostgresRepositoryBase


class PostgresFlowEventRepository(PostgresRepositoryBase):
    row = FormFlowEventRow
    document = FlowEventDocument

    async def add(
        self, form_id: str, session_id: str, from_page: str, to_page: str
    ) -> FlowEventDocument:
        return await self.upsert(
            FlowEventDocument(
                form_id=form_id,
                session_id=session_id,
                from_page=from_page,
                to_page=to_page,
            )
        )

    async def list_by_form_id(self, form_id: str) -> List[FlowEventDocument]:
        return await self.many(FormFlowEventRow.form_id == form_id)


class PostgresFormAIInsightRepository(PostgresRepositoryBase):
    row = FormAiInsightRow
    document = FormAIInsightDocument

    async def find(
        self, workspace_id: PydanticObjectId, form_id: str
    ) -> Optional[FormAIInsightDocument]:
        return await self.one(
            FormAiInsightRow.workspace_id == _oid(workspace_id),
            FormAiInsightRow.form_id == form_id,
        )

    async def save(self, document: FormAIInsightDocument) -> FormAIInsightDocument:
        return await self.upsert(document)


class PostgresFormAISessionRepository(PostgresRepositoryBase):
    row = FormAiSessionRow
    document = FormAISessionDocument

    async def get_or_404(self, session_id: PydanticObjectId) -> FormAISessionDocument:
        return await self.get_or_raise(session_id)

    async def save(self, session: FormAISessionDocument) -> FormAISessionDocument:
        return await self.upsert(session)


class PostgresWorkspaceAIProfileRepository(PostgresRepositoryBase):
    row = WorkspaceAiProfileRow
    document = WorkspaceAIProfileDocument

    async def find_by_workspace(
        self, workspace_id: PydanticObjectId
    ) -> Optional[WorkspaceAIProfileDocument]:
        return await self.one(WorkspaceAiProfileRow.workspace_id == _oid(workspace_id))

    async def save(
        self, document: WorkspaceAIProfileDocument
    ) -> WorkspaceAIProfileDocument:
        return await self.upsert(document)


class PostgresAIPreferenceMemoryRepository(PostgresRepositoryBase):
    row = AiPreferenceMemoryRow
    document = UserAIPreferenceMemoryDocument

    async def find(
        self, workspace_id: PydanticObjectId, user_id: str
    ) -> Optional[UserAIPreferenceMemoryDocument]:
        return await self.one(
            AiPreferenceMemoryRow.workspace_id == _oid(workspace_id),
            AiPreferenceMemoryRow.user_id == user_id,
        )

    async def save(
        self, document: UserAIPreferenceMemoryDocument
    ) -> UserAIPreferenceMemoryDocument:
        return await self.upsert(document)


class PostgresMcpAuditLogRepository(PostgresRepositoryBase):
    row = McpAuditLogRow
    document = MCPAuditLogDocument

    async def add(self, **fields) -> MCPAuditLogDocument:
        return await self.upsert(MCPAuditLogDocument(**fields))

    async def list_by_workspace(
        self, workspace_id: PydanticObjectId
    ) -> List[MCPAuditLogDocument]:
        return await self.many(McpAuditLogRow.workspace_id == _oid(workspace_id))
