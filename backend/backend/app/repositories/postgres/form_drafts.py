"""The repository of saved form drafts (Postgres only, new in 4.2). A draft's
answers are one encrypted payload; this class stores and returns the
ciphertext and never decrypts, logs or queries it. Queries use the spine
columns of :mod:`backend.db.models`."""

import datetime as dt
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import select, tuple_

from backend.app.repositories.postgres.responses import _advisory_lock, _locked_doc
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

    async def count_live_anonymous_for_form(self, form_id, now: dt.datetime) -> int:
        return await self.count(
            FormDraftRow.form_id == _id(form_id),
            FormDraftRow.owner_id.is_(None),
            FormDraftRow.expires_at > now,
        )

    async def count_live_for_owner(self, owner_id, now: dt.datetime) -> int:
        return await self.count(
            FormDraftRow.owner_id == _id(owner_id), FormDraftRow.expires_at > now
        )

    async def update_fields(
        self, workspace_id, form_id, draft_id, touch: bool = True, **fields
    ) -> Optional[FormDraftDocument]:
        """Change only the named fields of an existing draft, and nothing else.

        The row is locked and read afresh, so what another request changed meanwhile
        (a link request's token and edit key, a save's answers) is kept and never
        written back from an older copy; it is filtered by id, workspace and form;
        and it never inserts: a draft deleted meanwhile (discard, the submit,
        the purge) stays deleted. ``None`` when there is no such draft. ``touch``
        moves ``updated_at`` (a save does, taking the edit key does not)."""
        async with self._session() as session, session.begin():
            draft = await _locked_doc(
                session,
                FormDraftRow,
                FormDraftRow.id == _id(draft_id),
                FormDraftRow.workspace_id == _id(workspace_id),
                FormDraftRow.form_id == _id(form_id),
                document=FormDraftDocument,
            )
            if draft is None:
                return None
            for name, value in fields.items():
                setattr(draft, name, value)
            if touch:
                draft.touch()
            await session.execute(self._upsert_statement(row_values(draft)))
        return draft

    async def replace_edit_key(
        self, workspace_id, form_id, draft_id, edit_key_hash: str
    ) -> bool:
        """Set the edit key hash of a draft and nothing else (``updated_at``
        stays: "saved on" does not move). False when the draft is gone."""
        found = await self.update_fields(
            workspace_id, form_id, draft_id, touch=False, edit_key_hash=edit_key_hash
        )
        return found is not None

    async def delete_beyond_retention(
        self, workspace_id, form_id, last_saved_before: dt.datetime
    ) -> int:
        """Delete a form's drafts last saved at or before ``last_saved_before``
        (the form's retention was lowered since they were saved)."""
        return await self.delete_where(
            FormDraftRow.workspace_id == _id(workspace_id),
            FormDraftRow.form_id == _id(form_id),
            FormDraftRow.updated_at <= last_saved_before,
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

    async def form_keys(
        self, after: Optional[Tuple[str, str]] = None, limit: int = 1000
    ) -> List[Tuple[str, str]]:
        """A page of the (workspace id, form id) pairs that hold drafts, in
        order, after ``after`` (the purge pages through all of them and asks
        whether each form still takes drafts)."""
        statement = select(FormDraftRow.workspace_id, FormDraftRow.form_id).distinct()
        if after is not None:
            statement = statement.where(
                tuple_(FormDraftRow.workspace_id, FormDraftRow.form_id) > tuple_(*after)
            )
        statement = statement.order_by(
            FormDraftRow.workspace_id, FormDraftRow.form_id
        ).limit(limit)
        async with self._session() as session:
            rows = (await session.execute(statement)).all()
        return [(str(w), str(f)) for w, f in rows]
