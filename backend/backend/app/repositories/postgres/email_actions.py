"""Repository of a form's email actions (Postgres only, new in 4.2). Queries
use the spine columns of :mod:`backend.db.models`. The deliveries are rows of
the shared action log (``PostgresActionLogRepository``)."""

from typing import List, Optional, Sequence

from sqlalchemy import text

from backend.app.schemas.email_action import FormEmailActionDocument
from backend.db.models import FormEmailActionRow
from common.records.repository import RecordRepository


def _id(value) -> str:
    return str(value)


class PostgresFormEmailActionRepository(RecordRepository):
    row = FormEmailActionRow
    document = FormEmailActionDocument

    async def get(
        self, workspace_id, form_id, action_id
    ) -> Optional[FormEmailActionDocument]:
        """Only an action of this form of this workspace."""
        return await self.one(
            FormEmailActionRow.id == _id(action_id),
            FormEmailActionRow.workspace_id == _id(workspace_id),
            FormEmailActionRow.form_id == _id(form_id),
        )

    async def list_for_form(self, workspace_id, form_id) -> List[FormEmailActionDocument]:
        return await self.many(
            FormEmailActionRow.workspace_id == _id(workspace_id),
            FormEmailActionRow.form_id == _id(form_id),
            order_by=(FormEmailActionRow.created_at, FormEmailActionRow.id),
        )

    async def list_with_team_address(
        self, folded_address: str, workspace_id=None
    ) -> List[FormEmailActionDocument]:
        """The actions whose team lists the address (compared lower-cased, of
        one workspace when given, else of every workspace)."""
        where = [
            text(
                "EXISTS (SELECT 1 FROM jsonb_array_elements_text(doc -> 'team_recipients') "
                "AS member(address) WHERE lower(member.address) = :address)"
            ).bindparams(address=folded_address.lower())
        ]
        if workspace_id is not None:
            where.append(FormEmailActionRow.workspace_id == _id(workspace_id))
        return await self.many(*where)

    async def count_for_form(self, workspace_id, form_id) -> int:
        return await self.count(
            FormEmailActionRow.workspace_id == _id(workspace_id),
            FormEmailActionRow.form_id == _id(form_id),
        )

    async def save(self, document: FormEmailActionDocument) -> FormEmailActionDocument:
        return await self.save_document(document)

    async def delete(self, workspace_id, form_id, action_id) -> int:
        return await self.delete_where(
            FormEmailActionRow.id == _id(action_id),
            FormEmailActionRow.workspace_id == _id(workspace_id),
            FormEmailActionRow.form_id == _id(form_id),
        )

    async def delete_for_form(self, workspace_id, form_id) -> int:
        return await self.delete_where(
            FormEmailActionRow.workspace_id == _id(workspace_id),
            FormEmailActionRow.form_id == _id(form_id),
        )

    async def delete_by_form_ids(self, form_ids: Sequence) -> int:
        if not form_ids:
            return 0
        return await self.delete_where(
            FormEmailActionRow.form_id.in_([_id(f) for f in form_ids])
        )

    async def delete_by_workspace_ids(self, workspace_ids: Sequence) -> int:
        return await self.delete_where(
            FormEmailActionRow.workspace_id.in_([_id(w) for w in workspace_ids])
        )
