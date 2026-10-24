"""The ai group's repositories: Postgres only (its Mongo collections are read
only by the import from 4.0)."""

import datetime as dt
from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.app.schemas.ai_preference_memory import UserAIPreferenceMemoryDocument
from backend.app.schemas.create_form_prompts import CreateFormPrompt
from backend.app.schemas.api_idempotency_record import (
    IDEMPOTENCY_DONE,
    IDEMPOTENCY_PENDING,
    ApiIdempotencyRecordDocument,
)
from backend.app.schemas.form_ai_insight import FormAIInsightDocument
from backend.app.schemas.form_ai_session import FormAISessionDocument
from backend.app.schemas.mcp_audit_log import MCPAuditLogDocument
from backend.app.schemas.workspace_ai_profile import WorkspaceAIProfileDocument
from backend.db.models import (
    AiPreferenceMemoryRow,
    ApiIdempotencyKeyRow,
    CreateFormPromptRow,
    FormAiInsightRow,
    FormAiSessionRow,
    McpAuditLogRow,
    WorkspaceAiProfileRow,
)
from common.clock import utcnow
from common.records import RecordId, decode, row_values
from common.records.repository import RecordRepository


class PostgresFormAIInsightRepository(RecordRepository):
    row = FormAiInsightRow
    document = FormAIInsightDocument

    async def find(
        self, workspace_id: RecordId, form_id: str
    ) -> Optional[FormAIInsightDocument]:
        return await self.one(
            FormAiInsightRow.workspace_id == str(workspace_id),
            FormAiInsightRow.form_id == form_id,
        )

    async def save(self, document: FormAIInsightDocument) -> FormAIInsightDocument:
        return await self.save_document(document)


class PostgresFormAISessionRepository(RecordRepository):
    row = FormAiSessionRow
    document = FormAISessionDocument

    async def get_or_404(self, session_id: RecordId) -> FormAISessionDocument:
        """The session, or ``NotFoundError`` when there is none."""
        return await self.get_or_raise(session_id)

    async def save(self, session: FormAISessionDocument) -> FormAISessionDocument:
        return await self.save_document(session)

    async def update_proposal(
        self,
        session_id: RecordId,
        proposal_id: str,
        fields: dict,
        only_if_status: Optional[str] = None,
    ) -> bool:
        """Set ``fields`` on one proposal of a session's turns and nothing
        else. The row is locked, so a chat turn saved at the same time waits
        and then keeps this change only if it read the row afterwards. With
        ``only_if_status``, only while the proposal has that status.

        Every proposal record with this id that passes the status filter is
        updated, and the answer is whether anything changed: setting values
        that are already there is not an update."""
        locked = (
            select(FormAiSessionRow.doc)
            .where(FormAiSessionRow.id == str(session_id))
            .with_for_update()
        )
        async with self._session() as session, session.begin():
            doc = (await session.execute(locked)).scalar_one_or_none()
            if doc is None:
                return False
            document = decode(FormAISessionDocument, doc)
            changed = False
            for message in document.messages or []:
                record = message.get("proposal")
                if not isinstance(record, dict) or record.get("id") != proposal_id:
                    continue
                if only_if_status is not None and record.get("status") != only_if_status:
                    continue
                for key, value in fields.items():
                    if key not in record or record[key] != value:
                        record[key] = value
                        changed = True
            if changed:
                await session.execute(self._upsert_statement(row_values(document)))
        return changed


class PostgresWorkspaceAIProfileRepository(RecordRepository):
    row = WorkspaceAiProfileRow
    document = WorkspaceAIProfileDocument

    async def find_by_workspace(
        self, workspace_id: RecordId
    ) -> Optional[WorkspaceAIProfileDocument]:
        return await self.one(WorkspaceAiProfileRow.workspace_id == str(workspace_id))

    async def save(
        self, document: WorkspaceAIProfileDocument
    ) -> WorkspaceAIProfileDocument:
        return await self.save_document(document)


class PostgresAIPreferenceMemoryRepository(RecordRepository):
    row = AiPreferenceMemoryRow
    document = UserAIPreferenceMemoryDocument

    async def find(
        self, workspace_id: RecordId, user_id: str
    ) -> Optional[UserAIPreferenceMemoryDocument]:
        return await self.one(
            AiPreferenceMemoryRow.workspace_id == str(workspace_id),
            AiPreferenceMemoryRow.user_id == user_id,
        )

    async def save(
        self, document: UserAIPreferenceMemoryDocument
    ) -> UserAIPreferenceMemoryDocument:
        return await self.save_document(document)


class PostgresMcpAuditLogRepository(RecordRepository):
    row = McpAuditLogRow
    document = MCPAuditLogDocument

    async def add(self, **fields) -> MCPAuditLogDocument:
        return await self.save_document(MCPAuditLogDocument(**fields))

    async def list_by_workspace(
        self, workspace_id: RecordId
    ) -> List[MCPAuditLogDocument]:
        return await self.many(McpAuditLogRow.workspace_id == str(workspace_id))


class PostgresCreateFormPromptRepository(RecordRepository):
    row = CreateFormPromptRow
    document = CreateFormPrompt

    async def add(self, prompt: CreateFormPrompt) -> CreateFormPrompt:
        return await self.save_document(prompt)

    async def list_by_form_id(
        self, form_id: RecordId
    ) -> List[CreateFormPrompt]:
        return await self.many(CreateFormPromptRow.form_id == str(form_id))


class PostgresIdempotencyRepository(RecordRepository):
    row = ApiIdempotencyKeyRow
    document = ApiIdempotencyRecordDocument

    async def find(self, record_id: str) -> Optional[ApiIdempotencyRecordDocument]:
        """The record, unless it expired (expired rows linger until the next
        claim sweeps them)."""
        return await self.one(
            ApiIdempotencyKeyRow.id == str(record_id),
            ApiIdempotencyKeyRow.expires_at > dt.datetime.now(dt.timezone.utc),
        )

    async def claim(self, record: ApiIdempotencyRecordDocument) -> bool:
        """Store ``record`` unless a live record has its id; True when this
        call stored it. Atomic: of two requests with the same key, one
        claims it."""
        now = utcnow()
        names = self._column_names()
        values = row_values(record)
        async with self._session() as session, session.begin():
            # an expired record gives way to the new one
            await session.execute(
                delete(ApiIdempotencyKeyRow).where(
                    ApiIdempotencyKeyRow.id == values["id"],
                    ApiIdempotencyKeyRow.expires_at <= now,
                )
            )
            inserted = await session.execute(
                pg_insert(ApiIdempotencyKeyRow)
                .values({names[k]: v for k, v in values.items()})
                .on_conflict_do_nothing(index_elements=[names["id"]])
                .returning(ApiIdempotencyKeyRow.id)
            )
            claimed = inserted.scalar_one_or_none() is not None
        if claimed:
            # no TTL index here: expired records go whenever a new one is stored
            await self.delete_where(ApiIdempotencyKeyRow.expires_at <= now)
        return claimed

    async def complete(
        self,
        record_id: str,
        status_code: int,
        body: str,
        etag: Optional[str] = None,
    ) -> None:
        """Keep the response of the request that claimed ``record_id``."""
        locked = (
            select(ApiIdempotencyKeyRow.doc)
            .where(ApiIdempotencyKeyRow.id == str(record_id))
            .with_for_update()
        )
        async with self._session() as session, session.begin():
            doc = (await session.execute(locked)).scalar_one_or_none()
            if doc is None:
                return
            record = decode(ApiIdempotencyRecordDocument, doc)
            if record.state != IDEMPOTENCY_PENDING:
                return
            record.state = IDEMPOTENCY_DONE
            record.status_code = status_code
            record.body = body
            record.etag = etag
            record.updated_at = utcnow()
            await session.execute(self._upsert_statement(row_values(record)))

    async def release(self, record_id: str) -> None:
        """Forget a claim whose request failed on our side, so a retry runs."""
        record = await self.one(ApiIdempotencyKeyRow.id == str(record_id))
        if record is not None and record.state == IDEMPOTENCY_PENDING:
            await self.delete_where(ApiIdempotencyKeyRow.id == str(record_id))
