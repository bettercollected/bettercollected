"""The repository of the revision log of responses (Postgres only, new in
4.3). The entries are *written* by ``PostgresFormResponseRepository.
patch_form_response``, in the transaction that merges the answers (so a
change and its entry commit or roll back together); this repository reads
them and replaces a deleted account's id. Nothing here decrypts a value."""

from typing import List, Optional

from sqlalchemy import select

from backend.app.schemas.response_revision import (
    DELETED_ACTOR,
    ActorKind,
    ResponseRevisionDocument,
)
from backend.db.models import ResponseRevisionRow
from common.records.codec import decode, row_values
from common.records.repository import RecordRepository


class PostgresResponseRevisionRepository(RecordRepository):
    row = ResponseRevisionRow
    document = ResponseRevisionDocument

    async def list_for_response(self, response_pk) -> List[ResponseRevisionDocument]:
        """The entries of one response, oldest first."""
        return await self.many(
            ResponseRevisionRow.response_pk == str(response_pk),
            order_by=(ResponseRevisionRow.seq, ResponseRevisionRow.id),
        )

    async def get(self, response_pk, seq: int) -> Optional[ResponseRevisionDocument]:
        return await self.one(
            ResponseRevisionRow.response_pk == str(response_pk),
            ResponseRevisionRow.seq == int(seq),
        )

    async def forget_actor(self, user_id) -> int:
        """The staff member's account was deleted: their entries stay (what
        changed, when, with the role), with the user replaced by
        ``DELETED_ACTOR``. Returns the entries changed."""
        changed = 0
        for found in await self.many(
            ResponseRevisionRow.actor_id == str(user_id),
            ResponseRevisionRow.doc["actor_kind"].astext == ActorKind.STAFF.value,
        ):
            async with self._session() as session, session.begin():
                doc = (
                    await session.execute(
                        select(ResponseRevisionRow.doc)
                        .where(ResponseRevisionRow.id == str(found.id))
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if doc is None:
                    continue
                document = decode(self.document, doc)
                if document.actor_id != str(user_id):
                    continue
                document.actor_id = DELETED_ACTOR
                # only the user is replaced: the time of the edit stays
                await session.execute(self._upsert_statement(row_values(document)))
                changed += 1
        return changed
