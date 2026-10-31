"""Repositories of the webhook feature (Postgres only, new in 4.2): a form's
webhooks, the action log and the audit trail. Queries use the spine columns of
:mod:`backend.db.models`. A log row never holds answer data."""

import datetime as dt
from typing import Iterable, List, Optional, Sequence

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.app.schemas.webhook import (
    ActionLogDocument,
    ActionType,
    FormWebhookDocument,
    LogStatus,
    WebhookAuditDocument,
)
from backend.db.models import ActionLogRow, FormWebhookRow, WebhookAuditRow
from common.records.codec import decode, row_values
from common.records.repository import RecordRepository


def _id(value) -> str:
    return str(value)


class PostgresFormWebhookRepository(RecordRepository):
    row = FormWebhookRow
    document = FormWebhookDocument

    async def get(self, workspace_id, form_id, webhook_id) -> Optional[FormWebhookDocument]:
        """Only a webhook of this form of this workspace."""
        return await self.one(
            FormWebhookRow.id == _id(webhook_id),
            FormWebhookRow.workspace_id == _id(workspace_id),
            FormWebhookRow.form_id == _id(form_id),
        )

    async def get_by_id(self, webhook_id) -> Optional[FormWebhookDocument]:
        return await self.one(FormWebhookRow.id == _id(webhook_id))

    async def list_for_form(self, workspace_id, form_id) -> List[FormWebhookDocument]:
        return await self.many(
            FormWebhookRow.workspace_id == _id(workspace_id),
            FormWebhookRow.form_id == _id(form_id),
            order_by=(FormWebhookRow.created_at, FormWebhookRow.id),
        )

    async def count_for_form(self, workspace_id, form_id) -> int:
        return await self.count(
            FormWebhookRow.workspace_id == _id(workspace_id),
            FormWebhookRow.form_id == _id(form_id),
        )

    async def save(self, document: FormWebhookDocument) -> FormWebhookDocument:
        return await self.save_document(document)

    async def delete(self, workspace_id, form_id, webhook_id) -> int:
        return await self.delete_where(
            FormWebhookRow.id == _id(webhook_id),
            FormWebhookRow.workspace_id == _id(workspace_id),
            FormWebhookRow.form_id == _id(form_id),
        )

    async def delete_for_form(self, workspace_id, form_id) -> int:
        return await self.delete_where(
            FormWebhookRow.workspace_id == _id(workspace_id),
            FormWebhookRow.form_id == _id(form_id),
        )

    async def delete_by_form_ids(self, form_ids: Sequence) -> int:
        if not form_ids:
            return 0
        return await self.delete_where(
            FormWebhookRow.form_id.in_([_id(f) for f in form_ids])
        )

    async def delete_by_workspace_ids(self, workspace_ids: Sequence) -> int:
        return await self.delete_where(
            FormWebhookRow.workspace_id.in_([_id(w) for w in workspace_ids])
        )


class PostgresActionLogRepository(RecordRepository):
    row = ActionLogRow
    document = ActionLogDocument

    async def create_if_absent(self, document: ActionLogDocument) -> Optional[ActionLogDocument]:
        """Insert unless this action already has a run for the response (the
        idempotency key): the document, or None when one exists."""
        document.ensure_id()
        values = row_values(document)
        names = self._column_names()
        async with self._session() as session, session.begin():
            result = await session.execute(
                pg_insert(self.row)
                .values({names[k]: v for k, v in values.items()})
                .on_conflict_do_nothing()
                .returning(self.row.id)
            )
            inserted = result.first() is not None
        return document if inserted else None

    async def create(self, document: ActionLogDocument) -> ActionLogDocument:
        return await self.upsert(document)

    async def get(self, log_id) -> Optional[ActionLogDocument]:
        return await self.one(ActionLogRow.id == _id(log_id))

    async def save_existing(self, document: ActionLogDocument) -> bool:
        """Store ``document`` only if its row still exists (an UPDATE by id,
        never an insert): a run deleted meanwhile (its form was deleted) is not
        brought back. False when the row is gone."""
        document.touch()
        values = row_values(document)
        names = self._column_names()
        async with self._session() as session, session.begin():
            table = self.row.__table__
            result = await session.execute(
                update(table)
                .where(table.c.id == _id(document.id))
                .values(
                    {
                        names[key]: values[key]
                        for key in ("doc", "updated_at", "bc_source", "bc_checksum")
                    }
                )
                .returning(table.c.id)
            )
            return result.first() is not None

    async def claim(
        self, log_id, allowed: Iterable[LogStatus], *, now: dt.datetime
    ) -> Optional[ActionLogDocument]:
        """Atomically move a run that is in one of ``allowed`` to
        ``in_progress`` (one attempt more); None when it is in another state,
        i.e. delivered, failed, or being handled by another job."""
        statuses = [s.value for s in allowed]
        async with self._session() as session, session.begin():
            doc = (
                await session.execute(
                    select(self.row.doc)
                    .where(ActionLogRow.id == _id(log_id), ActionLogRow.status.in_(statuses))
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                return None
            claimed = decode(self.document, doc)
            claimed.status = LogStatus.IN_PROGRESS
            claimed.attempts += 1
            claimed.last_attempt_at = now
            claimed.first_attempt_at = claimed.first_attempt_at or now
            claimed.touch()
            await session.execute(self._upsert_statement(row_values(claimed)))
        return claimed

    async def list_for_form(
        self,
        workspace_id,
        form_id,
        *,
        statuses: Optional[Sequence[str]] = None,
        limit: int = 50,
        offset: int = 0,
        action_type: ActionType = ActionType.WEBHOOK,
    ) -> List[ActionLogDocument]:
        where = self._form_where(workspace_id, form_id, statuses, action_type)
        async with self._session() as session:
            docs = (
                (
                    await session.execute(
                        select(self.row.doc)
                        .where(*where)
                        .order_by(ActionLogRow.created_at.desc(), ActionLogRow.id.desc())
                        .limit(limit)
                        .offset(offset)
                    )
                )
                .scalars()
                .all()
            )
        return [decode(self.document, d) for d in docs]

    async def count_for_form(
        self, workspace_id, form_id, statuses=None, action_type=ActionType.WEBHOOK
    ) -> int:
        return await self.count(
            *self._form_where(workspace_id, form_id, statuses, action_type)
        )

    @staticmethod
    def _of_type(action_type: ActionType):
        """Rows of one kind of action (a row without a type is a webhook's)."""
        if action_type is ActionType.WEBHOOK:
            return or_(
                ActionLogRow.action_type == ActionType.WEBHOOK.value,
                ActionLogRow.action_type.is_(None),
            )
        return ActionLogRow.action_type == action_type.value

    @classmethod
    def _form_where(cls, workspace_id, form_id, statuses, action_type=ActionType.WEBHOOK):
        where = [
            ActionLogRow.workspace_id == _id(workspace_id),
            ActionLogRow.form_id == _id(form_id),
            cls._of_type(action_type),
        ]
        if statuses:
            where.append(ActionLogRow.status.in_(list(statuses)))
        return where

    async def list_pending_before(
        self,
        created_before: dt.datetime,
        limit: int,
        action_type: ActionType = ActionType.WEBHOOK,
    ) -> List[ActionLogDocument]:
        return await self.many(
            ActionLogRow.status == LogStatus.PENDING.value,
            ActionLogRow.created_at < created_before,
            self._of_type(action_type),
            order_by=(ActionLogRow.created_at, ActionLogRow.id),
            limit=limit,
        )

    async def list_stuck(
        self,
        status: LogStatus,
        updated_before: dt.datetime,
        limit: int,
        action_type: ActionType = ActionType.WEBHOOK,
    ) -> List[ActionLogDocument]:
        """``in_progress`` or ``retrying`` rows that did not move for a while:
        the worker died, or the job of a retry is gone."""
        return await self.many(
            ActionLogRow.status == status.value,
            ActionLogRow.updated_at < updated_before,
            self._of_type(action_type),
            order_by=(ActionLogRow.updated_at, ActionLogRow.id),
            limit=limit,
        )

    async def purge_before(self, cutoff: dt.datetime) -> int:
        """Delete every row created before ``cutoff`` (the 30-day retention)."""
        return await self.delete_where(ActionLogRow.created_at < cutoff)

    async def delete_by_response_id(self, workspace_id, form_id, response_id) -> int:
        """The rows of one response of one form of one workspace (a response id
        alone is not scoped: a response is stored once per workspace)."""
        return await self.delete_where(
            ActionLogRow.workspace_id == _id(workspace_id),
            ActionLogRow.form_id == _id(form_id),
            ActionLogRow.response_id == _id(response_id),
        )

    async def delete_for_form(self, workspace_id, form_id) -> int:
        return await self.delete_where(
            ActionLogRow.workspace_id == _id(workspace_id),
            ActionLogRow.form_id == _id(form_id),
        )

    async def delete_by_form_ids(self, form_ids: Sequence) -> int:
        if not form_ids:
            return 0
        return await self.delete_where(ActionLogRow.form_id.in_([_id(f) for f in form_ids]))

    async def delete_by_action(self, action_id) -> int:
        return await self.delete_where(ActionLogRow.action_id == _id(action_id))

    async def delete_by_workspace_ids(self, workspace_ids: Sequence) -> int:
        return await self.delete_where(
            ActionLogRow.workspace_id.in_([_id(w) for w in workspace_ids])
        )


class PostgresWebhookAuditRepository(RecordRepository):
    row = WebhookAuditRow
    document = WebhookAuditDocument

    async def add(self, document: WebhookAuditDocument) -> WebhookAuditDocument:
        return await self.upsert(document)

    async def list_for_form(self, workspace_id, form_id, limit: int = 20) -> List[WebhookAuditDocument]:
        async with self._session() as session:
            docs = (
                (
                    await session.execute(
                        select(self.row.doc)
                        .where(
                            WebhookAuditRow.workspace_id == _id(workspace_id),
                            WebhookAuditRow.form_id == _id(form_id),
                        )
                        .order_by(WebhookAuditRow.created_at.desc(), WebhookAuditRow.id.desc())
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
        return [decode(self.document, d) for d in docs]

    async def delete_for_form(self, workspace_id, form_id) -> int:
        return await self.delete_where(
            WebhookAuditRow.workspace_id == _id(workspace_id),
            WebhookAuditRow.form_id == _id(form_id),
        )

    async def delete_by_form_ids(self, form_ids: Sequence) -> int:
        if not form_ids:
            return 0
        return await self.delete_where(WebhookAuditRow.form_id.in_([_id(f) for f in form_ids]))

    async def delete_by_workspace_ids(self, workspace_ids: Sequence) -> int:
        return await self.delete_where(
            WebhookAuditRow.workspace_id.in_([_id(w) for w in workspace_ids])
        )
