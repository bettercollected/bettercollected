"""The repository of member groups ("Teams") and their members (Postgres
only, new in 4.4; ``FORM_ACCESS_ENABLED``).

Every query carries the workspace id, so a team or a membership can never be
reached across workspaces.
"""

from typing import List, Optional

from common.records import RecordId, derived_id
from sqlalchemy import select

from backend.app.schemas.member_group import (
    MemberGroupDocument,
    MemberGroupMemberDocument,
    name_key,
)
from backend.db.models import MemberGroupMemberRow, MemberGroupRow
from common.records.repository import RecordRepository


def _id(value) -> str:
    return str(value)


class PostgresMemberGroupRepository(RecordRepository):
    row = MemberGroupRow
    document = MemberGroupDocument

    # -- teams -----------------------------------------------------------------
    async def find(
        self, workspace_id, group_id
    ) -> Optional[MemberGroupDocument]:
        return await self.one(
            MemberGroupRow.workspace_id == _id(workspace_id),
            MemberGroupRow.id == _id(group_id),
        )

    async def find_by_name(
        self, workspace_id, name: str
    ) -> Optional[MemberGroupDocument]:
        return await self.one(
            MemberGroupRow.workspace_id == _id(workspace_id),
            MemberGroupRow.name_key == name_key(name),
        )

    async def list_in_workspace(self, workspace_id) -> List[MemberGroupDocument]:
        return await self.many(MemberGroupRow.workspace_id == _id(workspace_id))

    async def save(self, group: MemberGroupDocument) -> MemberGroupDocument:
        """Insert or update; a second team of the workspace with the same
        (case-folded) name violates ``uq_member_groups_workspace_id_name_key``
        (``IntegrityError``)."""
        return await self.save_document(group)

    async def delete(self, workspace_id, group_id) -> bool:
        """The team and its member rows, in one transaction. Grants naming the
        team are the grant repository's to drop (the service does both)."""
        async with self._session() as session, session.begin():
            deleted = await self._delete_recorded(
                session,
                MemberGroupRow,
                MemberGroupRow.workspace_id == _id(workspace_id),
                MemberGroupRow.id == _id(group_id),
            )
            if deleted:
                await self._delete_recorded(
                    session,
                    MemberGroupMemberRow,
                    MemberGroupMemberRow.workspace_id == _id(workspace_id),
                    MemberGroupMemberRow.group_id == _id(group_id),
                )
        return bool(deleted)

    # -- members of a manual team ----------------------------------------------
    async def add_member(self, workspace_id, group_id, user_id) -> None:
        """Idempotent: the row id is derived from the pair."""
        await self.upsert(
            MemberGroupMemberDocument(
                id=derived_id("member_group_member", _id(group_id), _id(user_id)),
                group_id=RecordId(_id(group_id)),
                workspace_id=RecordId(_id(workspace_id)),
                user_id=_id(user_id),
            ),
            row=MemberGroupMemberRow,
        )

    async def remove_member(self, workspace_id, group_id, user_id) -> int:
        return await self.delete_where(
            MemberGroupMemberRow.workspace_id == _id(workspace_id),
            MemberGroupMemberRow.group_id == _id(group_id),
            MemberGroupMemberRow.user_id == _id(user_id),
            row=MemberGroupMemberRow,
        )

    async def member_ids(self, workspace_id, group_id) -> List[str]:
        async with self._session() as session:
            rows = await session.execute(
                select(MemberGroupMemberRow.user_id)
                .where(
                    MemberGroupMemberRow.workspace_id == _id(workspace_id),
                    MemberGroupMemberRow.group_id == _id(group_id),
                )
                .order_by(MemberGroupMemberRow.created_at, MemberGroupMemberRow.id)
            )
        return list(rows.scalars().all())

    async def group_ids_of(self, workspace_id, user_id) -> List[str]:
        """The teams of the workspace ``user_id`` is a (manual) member of."""
        async with self._session() as session:
            rows = await session.execute(
                select(MemberGroupMemberRow.group_id).where(
                    MemberGroupMemberRow.workspace_id == _id(workspace_id),
                    MemberGroupMemberRow.user_id == _id(user_id),
                )
            )
        return list(rows.scalars().all())
