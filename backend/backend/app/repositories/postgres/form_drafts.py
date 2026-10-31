"""The repository of saved form drafts (Postgres only, new in 4.2). A draft's
answers are one encrypted payload; this class stores and returns the
ciphertext and never decrypts, logs or queries it. Queries use the spine
columns of :mod:`backend.db.models`."""

import datetime as dt
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import select

from backend.app.repositories.postgres.responses import _advisory_lock
from backend.app.schemas.form_draft import FormDraftDocument
from backend.db.models import FormDraftRow
from common.records.codec import row_values
from common.records.repository import RecordRepository


def _id(value) -> str:
    return str(value)


class PostgresFormDraftRepository(RecordRepository):
    row = FormDraftRow
    document = FormDraftDocument

    async def get(self, workspace_id, form_id, draft_id) -> Optional[FormDraftDocument]:
        """Only a draft of this form of this workspace."""
        return await self.one(
            FormDraftRow.id == _id(draft_id),
            FormDraftRow.workspace_id == _id(workspace_id),
            FormDraftRow.form_id == _id(form_id),
        )

    async def for_owner(
        self, workspace_id, form_id, owner_id
    ) -> Optional[FormDraftDocument]:
        return await self.one(
            FormDraftRow.workspace_id == _id(workspace_id),
            FormDraftRow.form_id == _id(form_id),
            FormDraftRow.owner_id == _id(owner_id),
        )

    async def count_live_for_address(
        self, form_id, email_key: str, now: dt.datetime
    ) -> int:
        return await self.count(
            FormDraftRow.form_id == _id(form_id),
            FormDraftRow.email_key == email_key,
            FormDraftRow.expires_at > now,
        )

    async def save(self, document: FormDraftDocument) -> FormDraftDocument:
        return await self.save_document(document)

    async def create_for_address(
        self, document: FormDraftDocument, limit: int, now: dt.datetime
    ) -> Optional[FormDraftDocument]:
        """Insert a draft of an address unless it already holds ``limit`` live
        ones on the form (counted and inserted under one lock): the draft, or
        None when the address is at its limit."""
        document.ensure_id()
        async with self._session() as session, session.begin():
            await _advisory_lock(
                session, "form-draft-address", document.form_id, document.email_key
            )
            stored = len(
                (
                    await session.execute(
                        select(FormDraftRow.id).where(
                            FormDraftRow.form_id == _id(document.form_id),
                            FormDraftRow.email_key == document.email_key,
                            FormDraftRow.expires_at > now,
                        )
                    )
                )
                .scalars()
                .all()
            )
            if stored >= limit:
                return None
            document.touch()
            await session.execute(self._upsert_statement(row_values(document)))
        return document

    async def delete(self, workspace_id, form_id, draft_id) -> int:
        return await self.delete_where(
            FormDraftRow.id == _id(draft_id),
            FormDraftRow.workspace_id == _id(workspace_id),
            FormDraftRow.form_id == _id(form_id),
        )

    async def delete_for_owner(self, workspace_id, form_id, owner_id) -> int:
        return await self.delete_where(
            FormDraftRow.workspace_id == _id(workspace_id),
            FormDraftRow.form_id == _id(form_id),
            FormDraftRow.owner_id == _id(owner_id),
        )

    async def delete_by_owner(self, owner_id) -> int:
        """Every draft of an account, in every workspace (account deletion)."""
        return await self.delete_where(FormDraftRow.owner_id == _id(owner_id))

    async def delete_for_form(self, workspace_id, form_id) -> int:
        return await self.delete_where(
            FormDraftRow.workspace_id == _id(workspace_id),
            FormDraftRow.form_id == _id(form_id),
        )

    async def delete_by_form_ids(self, form_ids: Sequence) -> int:
        if not form_ids:
            return 0
        return await self.delete_where(
            FormDraftRow.form_id.in_([_id(f) for f in form_ids])
        )

    async def delete_by_workspace_ids(self, workspace_ids: Sequence) -> int:
        if not workspace_ids:
            return 0
        return await self.delete_where(
            FormDraftRow.workspace_id.in_([_id(w) for w in workspace_ids])
        )

    async def delete_expired(self, now: dt.datetime) -> int:
        return await self.delete_where(FormDraftRow.expires_at <= now)

    async def form_keys(self, limit: int = 5000) -> List[Tuple[str, str]]:
        """The (workspace id, form id) pairs that hold drafts (the purge asks
        whether each form still takes them)."""
        async with self._session() as session:
            rows = (
                await session.execute(
                    select(FormDraftRow.workspace_id, FormDraftRow.form_id)
                    .distinct()
                    .limit(limit)
                )
            ).all()
        return [(str(w), str(f)) for w, f in rows]
