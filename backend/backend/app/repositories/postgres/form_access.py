"""The repository of form grants (Postgres only, new in 4.4;
``FORM_ACCESS_ENABLED``).

Every query carries the workspace id, and the form id wherever the caller names
one, so a grant can never be read or changed across workspaces or forms.
"""

from typing import Iterable, List, Optional

from common.records import derived_id
from common.records.repository import RecordRepository
from sqlalchemy import and_, or_, select

from backend.app.schemas.form_access_grant import (
    SUBJECT_GROUP,
    SUBJECT_USER,
    FormAccessGrantDocument,
)
from backend.db.models import FormAccessGrantRow, MemberGroupMemberRow


def _id(value) -> str:
    return str(value)


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
        workspaces, and a grant never reaches across them."""
        grant.id = derived_id(
            "form_access_grant",
            grant.workspace_id,
            grant.form_id,
            grant.subject_type,
            grant.subject_id,
        )
        return await self.save_document(grant)

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
