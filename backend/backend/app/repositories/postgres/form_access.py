"""The repository of form grants (Postgres only, new in 4.4;
``FORM_ACCESS_ENABLED``).

Every query carries the workspace id, and the form id wherever the caller names
one, so a grant can never be read or changed across workspaces or forms.
"""

from typing import Dict, Iterable, List, Optional

from common.records import RecordId, derived_id, row_values
from common.records.repository import RecordRepository
from sqlalchemy import and_, or_, select

from backend.app.schemas.form_access_grant import (
    MEMBER_SUBJECTS,
    SUBJECT_GROUP,
    SUBJECT_KEY,
    SUBJECT_USER,
    FormAccessGrantDocument,
)
from backend.db.models import (
    FormAccessGrantRow,
    MemberGroupMemberRow,
    MemberGroupRow,
    WorkspaceApiKeyRow,
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

    async def held_on_form(
        self, workspace_id, form_id
    ) -> Dict[str, List[FormAccessGrantDocument]]:
        """Every grant of one form by the user who holds it, directly or through
        a team (a user holding it twice is listed under both): what the decision
        for all the members needs, in two queries however many members and
        teams there are."""
        held: Dict[str, List[FormAccessGrantDocument]] = {}
        grants = await self.list_for_form(workspace_id, form_id)
        teams: Dict[str, List[FormAccessGrantDocument]] = {}
        for grant in grants:
            if grant.subject_type == SUBJECT_USER:
                held.setdefault(str(grant.subject_id), []).append(grant)
            elif grant.subject_type == SUBJECT_GROUP:
                teams.setdefault(str(grant.subject_id), []).append(grant)
        if teams:
            async with self._session() as session:
                rows = await session.execute(
                    select(
                        MemberGroupMemberRow.group_id, MemberGroupMemberRow.user_id
                    ).where(
                        MemberGroupMemberRow.workspace_id == _id(workspace_id),
                        MemberGroupMemberRow.group_id.in_(list(teams)),
                    )
                )
            for group_id, user_id in rows.all():
                held.setdefault(str(user_id), []).extend(teams[str(group_id)])
        return held

    # -- the grants of a form --------------------------------------------------
    # What reads, finds or deletes "the grants of a form" for the member-facing
    # routes sees people and teams only: a key's row (``subject_type='key'``,
    # an API key's allow-list entry) is never listed, found or deleted here, so
    # a form's Editor can neither see nor remove it. Keys have their own
    # methods below.
    async def list_for_form(
        self, workspace_id, form_id
    ) -> List[FormAccessGrantDocument]:
        return await self.many(
            FormAccessGrantRow.workspace_id == _id(workspace_id),
            FormAccessGrantRow.form_id == _id(form_id),
            FormAccessGrantRow.subject_type.in_(MEMBER_SUBJECTS),
        )

    async def find(
        self, workspace_id, form_id, grant_id
    ) -> Optional[FormAccessGrantDocument]:
        return await self.one(
            FormAccessGrantRow.workspace_id == _id(workspace_id),
            FormAccessGrantRow.form_id == _id(form_id),
            FormAccessGrantRow.id == _id(grant_id),
            FormAccessGrantRow.subject_type.in_(MEMBER_SUBJECTS),
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
        """Delete a person's or a team's grant by id (never a key's row)."""
        return bool(
            await self.delete_where(
                FormAccessGrantRow.workspace_id == _id(workspace_id),
                FormAccessGrantRow.form_id == _id(form_id),
                FormAccessGrantRow.id == _id(grant_id),
                FormAccessGrantRow.subject_type.in_(MEMBER_SUBJECTS),
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

    # -- an API key's rows (``subject_type='key'``) ------------------------------
    async def for_key_on_form(
        self, workspace_id, key_id, form_id
    ) -> Optional[FormAccessGrantDocument]:
        """The key's row for one form, or ``None``: one indexed read, what a
        key limited to a list of forms is decided by."""
        return await self.one(
            FormAccessGrantRow.workspace_id == _id(workspace_id),
            FormAccessGrantRow.subject_type == SUBJECT_KEY,
            FormAccessGrantRow.subject_id == _id(key_id),
            FormAccessGrantRow.form_id == _id(form_id),
        )

    async def for_key(
        self, workspace_id, key_id, form_ids: Optional[Iterable[str]] = None
    ) -> List[FormAccessGrantDocument]:
        """The key's rows in the workspace (on ``form_ids`` only, when given):
        what a list filter needs, in one query."""
        where = [
            FormAccessGrantRow.workspace_id == _id(workspace_id),
            FormAccessGrantRow.subject_type == SUBJECT_KEY,
            FormAccessGrantRow.subject_id == _id(key_id),
        ]
        if form_ids is not None:
            where.append(FormAccessGrantRow.form_id.in_([_id(f) for f in form_ids]))
        return await self.many(*where)

    async def for_keys(
        self, workspace_id, key_ids: Iterable[str]
    ) -> List[FormAccessGrantDocument]:
        """The rows of several keys of the workspace, in one query (the keys
        page lists every key's forms)."""
        ids = [_id(k) for k in key_ids]
        if not ids:
            return []
        return await self.many(
            FormAccessGrantRow.workspace_id == _id(workspace_id),
            FormAccessGrantRow.subject_type == SUBJECT_KEY,
            FormAccessGrantRow.subject_id.in_(ids),
        )

    async def replace_for_key(
        self, workspace_id, key_id, rows: Iterable[FormAccessGrantDocument]
    ) -> List[FormAccessGrantDocument]:
        """Make ``rows`` the key's rows in the workspace, in one transaction:
        the rows not named go, the named ones are inserted or replaced (the row
        id is derived from workspace, form and key, so naming a form twice is
        one row). Refuses (``AccessTargetNotFound``) a key that is not an
        unrevoked key of the workspace and a form that is not linked to it,
        whatever the caller checked: the write keeps a row inside its workspace.
        A row is always written as a key row, whatever the document says."""
        async with self._session() as session, session.begin():
            return await self.replace_for_key_in(session, workspace_id, key_id, rows)

    async def form_ids_for_key_in(self, session, workspace_id, key_id) -> List[str]:
        """The ids of the forms the key holds a row for, sorted, read in the
        caller's transaction (under the key's row lock, a list nobody can change
        meanwhile)."""
        found = await session.execute(
            select(FormAccessGrantRow.form_id).where(
                FormAccessGrantRow.workspace_id == _id(workspace_id),
                FormAccessGrantRow.subject_type == SUBJECT_KEY,
                FormAccessGrantRow.subject_id == _id(key_id),
            )
        )
        return sorted(str(f) for f in found.scalars().all())

    async def delete_for_key_in(self, session, workspace_id, key_id) -> int:
        """Every row of the key, in the caller's transaction."""
        return await self._delete_recorded(
            session,
            FormAccessGrantRow,
            FormAccessGrantRow.workspace_id == _id(workspace_id),
            FormAccessGrantRow.subject_type == SUBJECT_KEY,
            FormAccessGrantRow.subject_id == _id(key_id),
        )

    async def replace_for_key_in(
        self, session, workspace_id, key_id, rows: Iterable[FormAccessGrantDocument]
    ) -> List[FormAccessGrantDocument]:
        """``replace_for_key`` in the caller's transaction (the key edit writes
        its rows under the key's row lock, in the transaction that stores the key
        and its audit entries)."""
        workspace_id, key_id = _id(workspace_id), _id(key_id)
        wanted: Dict[str, FormAccessGrantDocument] = {}
        for row in rows:
            row.workspace_id = RecordId(workspace_id)
            row.subject_type = SUBJECT_KEY
            row.subject_id = key_id
            row.form_id = _id(row.form_id)
            row.id = derived_id(
                "form_access_grant", workspace_id, row.form_id, SUBJECT_KEY, key_id
            )
            wanted[row.form_id] = row
        key = await session.execute(
            select(WorkspaceApiKeyRow.id)
            .where(
                WorkspaceApiKeyRow.id == key_id,
                WorkspaceApiKeyRow.workspace_id == workspace_id,
                WorkspaceApiKeyRow.revoked.is_not(True),
            )
            .limit(1)
            .with_for_update(read=True)
        )
        if key.first() is None:
            raise AccessTargetNotFound("key")
        if wanted:
            linked = await session.execute(
                select(WorkspaceFormRow.form_id)
                .where(
                    WorkspaceFormRow.workspace_id == workspace_id,
                    WorkspaceFormRow.form_id.in_(list(wanted)),
                )
                .with_for_update(read=True)
            )
            if {str(f) for f in linked.scalars().all()} != set(wanted):
                raise AccessTargetNotFound("form")
        await self._delete_recorded(
            session,
            FormAccessGrantRow,
            FormAccessGrantRow.workspace_id == workspace_id,
            FormAccessGrantRow.subject_type == SUBJECT_KEY,
            FormAccessGrantRow.subject_id == key_id,
            FormAccessGrantRow.form_id.not_in(list(wanted)),
        )
        for row in wanted.values():
            row.touch()
            await session.execute(
                self._upsert_statement(row_values(row), FormAccessGrantRow)
            )
        return list(wanted.values())

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
