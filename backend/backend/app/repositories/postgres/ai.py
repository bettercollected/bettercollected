"""Postgres twins of the ai- and analytics-group repositories."""

import datetime as dt
from typing import List, Optional

from beanie import PydanticObjectId
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.app.repositories.postgres.forms import _oid
from backend.app.schemas.ai_preference_memory import UserAIPreferenceMemoryDocument
from backend.app.schemas.create_form_prompts import CreateFormPrompt
from backend.app.schemas.api_idempotency_record import (
    IDEMPOTENCY_DONE,
    IDEMPOTENCY_PENDING,
    ApiIdempotencyRecordDocument,
)
from backend.app.schemas.flow_event import FlowEventDocument
from backend.app.schemas.form_ai_insight import FormAIInsightDocument
from backend.app.schemas.form_ai_session import FormAISessionDocument
from backend.app.schemas.mcp_audit_log import MCPAuditLogDocument
from backend.app.schemas.rate_limit_counter import RateLimitCounterDocument
from backend.app.schemas.workspace_ai_profile import WorkspaceAIProfileDocument
from backend.db.models import (
    AiPreferenceMemoryRow,
    ApiIdempotencyKeyRow,
    CreateFormPromptRow,
    FormAiInsightRow,
    FormAiSessionRow,
    FormFlowEventRow,
    McpAuditLogRow,
    RateLimitCounterRow,
    WorkspaceAiProfileRow,
)
from common.db import PostgresRepositoryBase, from_row_doc, row_values
from common.clock import utcnow


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

    async def delete_older_than(self, cutoff: dt.datetime) -> int:
        """Events recorded before ``cutoff``; uses the created_at index."""
        return await self.delete_where(FormFlowEventRow.created_at < cutoff)


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
        return await self.save_document(document)


class PostgresFormAISessionRepository(PostgresRepositoryBase):
    row = FormAiSessionRow
    document = FormAISessionDocument

    async def get_or_404(self, session_id: PydanticObjectId) -> FormAISessionDocument:
        return await self.get_or_raise(session_id)

    async def save(self, session: FormAISessionDocument) -> FormAISessionDocument:
        return await self.save_document(session)

    async def update_proposal(
        self,
        session_id: PydanticObjectId,
        proposal_id: str,
        fields: dict,
        only_if_status: Optional[str] = None,
    ) -> bool:
        """The Mongo original's targeted update: the row is locked, so a
        chat turn saved at the same time waits and then keeps this change
        only if it read the row afterwards (as with Mongo).

        Like the array-filtered ``$set``, every proposal record with this id
        that passes the status filter is updated, and the answer is whether
        anything changed (Mongo's ``modified_count``): setting values that are
        already there is not an update."""
        locked = (
            select(FormAiSessionRow.doc)
            .where(FormAiSessionRow.id == str(session_id))
            .with_for_update()
        )
        async with self._session() as session, session.begin():
            doc = (await session.execute(locked)).scalar_one_or_none()
            if doc is None:
                return False
            document = from_row_doc(FormAISessionDocument, doc)
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
        return await self.save_document(document)


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
        return await self.save_document(document)


class PostgresMcpAuditLogRepository(PostgresRepositoryBase):
    row = McpAuditLogRow
    document = MCPAuditLogDocument

    async def add(self, **fields) -> MCPAuditLogDocument:
        return await self.upsert(MCPAuditLogDocument(**fields))

    async def list_by_workspace(
        self, workspace_id: PydanticObjectId
    ) -> List[MCPAuditLogDocument]:
        return await self.many(McpAuditLogRow.workspace_id == _oid(workspace_id))


class PostgresCreateFormPromptRepository(PostgresRepositoryBase):
    row = CreateFormPromptRow
    document = CreateFormPrompt

    async def add(self, prompt: CreateFormPrompt) -> CreateFormPrompt:
        return await self.upsert(prompt)

    async def list_by_form_id(
        self, form_id: PydanticObjectId
    ) -> List[CreateFormPrompt]:
        return await self.many(CreateFormPromptRow.form_id == _oid(form_id))


class PostgresRateLimitRepository(PostgresRepositoryBase):
    row = RateLimitCounterRow
    document = RateLimitCounterDocument

    async def hit(
        self, counter_id: str, expires_at: dt.datetime, amount: int = 1
    ) -> int:
        now = utcnow()
        names = self._column_names()
        locked = (
            select(RateLimitCounterRow.doc)
            .where(RateLimitCounterRow.id == counter_id)
            .with_for_update()
        )
        async with self._session() as session, session.begin():
            doc = (await session.execute(locked)).scalar_one_or_none()
            if doc is None:
                first = RateLimitCounterDocument(
                    id=PydanticObjectId(counter_id),
                    hits=amount,
                    expires_at=expires_at,
                )
                values = row_values(first)
                inserted = await session.execute(
                    pg_insert(RateLimitCounterRow)
                    .values({names[k]: v for k, v in values.items()})
                    .on_conflict_do_nothing(index_elements=[names["id"]])
                    .returning(RateLimitCounterRow.id)
                )
                if inserted.scalar_one_or_none() is not None:
                    created = True
                else:
                    # another request created it first: count on that one
                    doc = (await session.execute(locked)).scalar_one()
                    created = False
            else:
                created = False
            if not created:
                counter = from_row_doc(RateLimitCounterDocument, doc)
                counter.hits += amount
                counter.updated_at = now
                await session.execute(self._upsert_statement(row_values(counter)))
                return counter.hits
        # no TTL index here: expired counters go whenever a new one starts
        await self.delete_where(RateLimitCounterRow.expires_at <= now)
        return amount


class PostgresIdempotencyRepository(PostgresRepositoryBase):
    row = ApiIdempotencyKeyRow
    document = ApiIdempotencyRecordDocument

    async def find(self, record_id: str) -> Optional[ApiIdempotencyRecordDocument]:
        return await self.one(
            ApiIdempotencyKeyRow.id == str(record_id),
            ApiIdempotencyKeyRow.expires_at > dt.datetime.now(dt.timezone.utc),
        )

    async def claim(self, record: ApiIdempotencyRecordDocument) -> bool:
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
        locked = (
            select(ApiIdempotencyKeyRow.doc)
            .where(ApiIdempotencyKeyRow.id == str(record_id))
            .with_for_update()
        )
        async with self._session() as session, session.begin():
            doc = (await session.execute(locked)).scalar_one_or_none()
            if doc is None:
                return
            record = from_row_doc(ApiIdempotencyRecordDocument, doc)
            if record.state != IDEMPOTENCY_PENDING:
                return
            record.state = IDEMPOTENCY_DONE
            record.status_code = status_code
            record.body = body
            record.etag = etag
            record.updated_at = utcnow()
            await session.execute(self._upsert_statement(row_values(record)))

    async def release(self, record_id: str) -> None:
        record = await self.one(ApiIdempotencyKeyRow.id == str(record_id))
        if record is not None and record.state == IDEMPOTENCY_PENDING:
            await self.delete_where(ApiIdempotencyKeyRow.id == str(record_id))
