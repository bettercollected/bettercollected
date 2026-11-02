"""Removing a member from a workspace, as one transaction: the membership, the
forms they created (handed to another member, so the workspace keeps its forms
and the removed person is nobody's creator any more), and their grants and team
memberships. Postgres only.

One transaction so a person is never half removed: no membership with their
grants gone, and no removed member whose grants would come back when they are
invited again.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from common.records import decode, row_values
from common.records.repository import RecordRepository
from sqlalchemy import select

from backend.app.schemas.form_access_grant import SUBJECT_USER
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.db.models import (
    FormAccessGrantRow,
    MemberGroupMemberRow,
    WorkspaceFormRow,
    WorkspaceUserRow,
)


def _id(value) -> str:
    return str(value)


@dataclass
class Removal:
    # the forms whose creator was the member, now the heir's
    forms: List[str] = field(default_factory=list)
    grants: int = 0
    teams: int = 0


class PostgresMemberRemovalRepository(RecordRepository):
    row = WorkspaceUserRow
    document = WorkspaceUserDocument

    async def forms_of(self, workspace_id, user_id) -> List[str]:
        """The ids of the workspace's forms whose creator is this member."""
        async with self._session() as session:
            rows = await session.execute(
                select(WorkspaceFormRow.form_id).where(
                    WorkspaceFormRow.workspace_id == _id(workspace_id),
                    WorkspaceFormRow.user_id == _id(user_id),
                )
            )
        return sorted(rows.scalars().all())

    async def remove(self, workspace_id, user_id, heir_id) -> Optional[Removal]:
        """Delete the membership, hand the member's forms in this workspace to
        ``heir_id``, drop their grants and team memberships. ``None`` when they
        are not a member."""
        ws, uid, heir = _id(workspace_id), _id(user_id), _id(heir_id)
        removal = Removal()
        async with self._session() as session, session.begin():
            gone = await self._delete_recorded(
                session,
                WorkspaceUserRow,
                WorkspaceUserRow.workspace_id == ws,
                WorkspaceUserRow.user_id == uid,
            )
            if not gone:
                return None
            links = (
                await session.execute(
                    select(WorkspaceFormRow.doc)
                    .where(
                        WorkspaceFormRow.workspace_id == ws,
                        WorkspaceFormRow.user_id == uid,
                    )
                    .order_by(WorkspaceFormRow.created_at, WorkspaceFormRow.id)
                    .with_for_update()
                )
            ).scalars().all()
            for doc in links:
                link = decode(WorkspaceFormDocument, doc)
                link.user_id = heir
                link.touch()
                await session.execute(
                    self._upsert_statement(row_values(link), WorkspaceFormRow)
                )
                removal.forms.append(str(link.form_id))
            removal.grants = await self._delete_recorded(
                session,
                FormAccessGrantRow,
                FormAccessGrantRow.workspace_id == ws,
                FormAccessGrantRow.subject_type == SUBJECT_USER,
                FormAccessGrantRow.subject_id == uid,
            )
            removal.teams = await self._delete_recorded(
                session,
                MemberGroupMemberRow,
                MemberGroupMemberRow.workspace_id == ws,
                MemberGroupMemberRow.user_id == uid,
            )
        await self._prune_tombstones_if_due(WorkspaceUserRow)
        removal.forms.sort()
        return removal
