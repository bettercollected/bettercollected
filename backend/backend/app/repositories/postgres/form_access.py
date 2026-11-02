"""The repository of form grants (Postgres only, new in 4.4;
``FORM_ACCESS_ENABLED``).

Every query carries the workspace id, and the form id wherever the caller names
one, so a grant can never be read or changed across workspaces or forms.
"""

from typing import Dict, Iterable, List, Optional

from common.records import derived_id, row_values
from common.records.repository import RecordRepository
from sqlalchemy import and_, or_, select

from backend.app.schemas.form_access_grant import (
    SUBJECT_GROUP,
    SUBJECT_USER,
    FormAccessGrantDocument,
)
from backend.db.models import (
    FormAccessGrantRow,
    MemberGroupMemberRow,
    MemberGroupRow,
    WorkspaceFormRow,
    WorkspaceUserRow,
)


def _id(value) -> str:
    return str(value)


class AccessTargetNotFound(LookupError):
    """What a write names is not in the workspace: ``what`` is ``form``,
    ``member`` or ``group``. The same error for "does not exist" and "belongs
    to another workspace": a caller never learns which."""

    def __init__(self, what: str):
        super().__init__(what)
        self.what = what


class PostgresFormAccessGrantRepository(RecordRepository):
    row = FormAccessGrantRow
    document = FormAccessGrantDocument

    @staticmethod
    def _held_by(workspace_id, user_id):
        """Rows naming the user, or a team the user is a manual member of: one
        condition, so one query however many teams there are."""
        teams = select(MemberGroupMemberRow.group_id).where(
            MemberGroupMemberRow.workspace_id == _id(workspace_id),
            MemberGroupMemberRow.user_id == _id(user_id),
        )
        return or_(
            and_(
                FormAccessGrantRow.subject_type == SUBJECT_USER,
                FormAccessGrantRow.subject_id == _id(user_id),
            ),
            and_(
                FormAccessGrantRow.subject_type == SUBJECT_GROUP,
                FormAccessGrantRow.subject_id.in_(teams),
            ),
        )

    # -- the decision (reads) --------------------------------------------------
    async def for_user_on_form(
        self, workspace_id, form_id, user_id
    ) -> List[FormAccessGrantDocument]:
        """The grants ``user_id`` holds on one form, directly and through teams."""
        return await self.many(
            FormAccessGrantRow.workspace_id == _id(workspace_id),
            FormAccessGrantRow.form_id == _id(form_id),
            self._held_by(workspace_id, user_id),
        )

    async def for_user(
        self, workspace_id, user_id, form_ids: Optional[Iterable[str]] = None
    ) -> List[FormAccessGrantDocument]:
        """The grants ``user_id`` holds in the workspace (on ``form_ids`` only,
        when given): what a list filter needs, in one query."""
        where = [
            FormAccessGrantRow.workspace_id == _id(workspace_id),
            self._held_by(workspace_id, user_id),
        ]
        if form_ids is not None:
            where.append(FormAccessGrantRow.form_id.in_([_id(f) for f in form_ids]))
        return await self.many(*where)

    # -- the grants of a form --------------------------------------------------
    async def list_for_form(
        self, workspace_id, form_id
    ) -> List[FormAccessGrantDocument]:
        return await self.many(
            FormAccessGrantRow.workspace_id == _id(workspace_id),
            FormAccessGrantRow.form_id == _id(form_id),
        )

    async def find(
        self, workspace_id, form_id, grant_id
    ) -> Optional[FormAccessGrantDocument]:
        return await self.one(
            FormAccessGrantRow.workspace_id == _id(workspace_id),
            FormAccessGrantRow.form_id == _id(form_id),
            FormAccessGrantRow.id == _id(grant_id),
        )

    async def put(self, grant: FormAccessGrantDocument) -> FormAccessGrantDocument:
        """Insert or replace the grant of (workspace, form, subject): the row id
        is derived from those, so a second grant to the same subject is the same
        row. The workspace is part of it: a form can be linked into two
        workspaces, and a grant never reaches across them.

        Refuses (``AccessTargetNotFound``) a form that is not linked to the
        workspace, a person who is not a member of it and a team of another
        workspace, whatever the caller checked before: the write itself keeps
        a grant inside its workspace."""
        grant.id = derived_id(
            "form_access_grant",
            grant.workspace_id,
            grant.form_id,
            grant.subject_type,
            grant.subject_id,
        )
        workspace_id = _id(grant.workspace_id)
        async with self._session() as session, session.begin():
            # shared locks: a form unlinked, a member removed or a team deleted
            # at the same moment waits for this write, which its own cleanup
            # then removes
            linked = await session.execute(
                select(WorkspaceFormRow.id)
                .where(
                    WorkspaceFormRow.workspace_id == workspace_id,
                    WorkspaceFormRow.form_id == _id(grant.form_id),
                )
                .limit(1)
                .with_for_update(read=True)
            )
            if linked.first() is None:
                raise AccessTargetNotFound("form")
            if grant.subject_type == SUBJECT_USER:
                subject = select(WorkspaceUserRow.id).where(
                    WorkspaceUserRow.workspace_id == workspace_id,
                    WorkspaceUserRow.user_id == _id(grant.subject_id),
                )
                what = "member"
            elif grant.subject_type == SUBJECT_GROUP:
                subject = select(MemberGroupRow.id).where(
                    MemberGroupRow.workspace_id == workspace_id,
                    MemberGroupRow.id == _id(grant.subject_id),
                )
                what = "group"
            else:
                raise AccessTargetNotFound("subject")
            found = await session.execute(subject.limit(1).with_for_update(read=True))
            if found.first() is None:
                raise AccessTargetNotFound(what)
            grant.touch()
            await session.execute(
                self._upsert_statement(row_values(grant), FormAccessGrantRow)
            )
        return grant

    # -- removal ---------------------------------------------------------------
    async def delete(self, workspace_id, form_id, grant_id) -> bool:
        return bool(
            await self.delete_where(
                FormAccessGrantRow.workspace_id == _id(workspace_id),
                FormAccessGrantRow.form_id == _id(form_id),
                FormAccessGrantRow.id == _id(grant_id),
            )
        )

    async def delete_for_form(self, workspace_id, form_id) -> int:
        return await self.delete_where(
            FormAccessGrantRow.workspace_id == _id(workspace_id),
            FormAccessGrantRow.form_id == _id(form_id),
        )

    async def delete_for_subject(
        self, workspace_id, subject_type: str, subject_id
    ) -> int:
        return await self.delete_where(
            FormAccessGrantRow.workspace_id == _id(workspace_id),
            FormAccessGrantRow.subject_type == subject_type,
            FormAccessGrantRow.subject_id == _id(subject_id),
        )

    async def delete_for_forms(self, form_ids: Iterable[str]) -> int:
        """Every grant on these forms, in any workspace (the forms are gone)."""
        ids = [_id(f) for f in form_ids]
        if not ids:
            return 0
        return await self.delete_where(FormAccessGrantRow.form_id.in_(ids))

    async def delete_for_workspaces(self, workspace_ids: Iterable) -> int:
        ids = [_id(w) for w in workspace_ids]
        if not ids:
            return 0
        return await self.delete_where(FormAccessGrantRow.workspace_id.in_(ids))

    # -- a person's grants (the Members page, removal) ---------------------------
    async def direct_for_user(self, workspace_id, user_id) -> List[FormAccessGrantDocument]:
        return await self.many(
            FormAccessGrantRow.workspace_id == _id(workspace_id),
            FormAccessGrantRow.subject_type == SUBJECT_USER,
            FormAccessGrantRow.subject_id == _id(user_id),
        )

    async def count_for_subject(self, workspace_id, subject_type: str, subject_id) -> int:
        return await self.count(
            FormAccessGrantRow.workspace_id == _id(workspace_id),
            FormAccessGrantRow.subject_type == subject_type,
            FormAccessGrantRow.subject_id == _id(subject_id),
        )

    async def delete_user_everywhere(self, user_id) -> Dict[str, int]:
        """Every direct grant of this person, in every workspace (their account
        is gone): the number removed per workspace."""
        rows = await self.many(
            FormAccessGrantRow.subject_type == SUBJECT_USER,
            FormAccessGrantRow.subject_id == _id(user_id),
        )
        per_workspace: Dict[str, int] = {}
        for row in rows:
            per_workspace[_id(row.workspace_id)] = (
                per_workspace.get(_id(row.workspace_id), 0) + 1
            )
        await self.delete_where(
            FormAccessGrantRow.subject_type == SUBJECT_USER,
            FormAccessGrantRow.subject_id == _id(user_id),
        )
        return per_workspace
