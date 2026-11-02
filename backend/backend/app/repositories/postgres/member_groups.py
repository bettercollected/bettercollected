"""The repository of member groups ("Teams") and their members (Postgres
only, new in 4.4; ``FORM_ACCESS_ENABLED``).

Every query carries the workspace id, so a team or a membership can never be
reached across workspaces.
"""

from typing import Dict, Iterable, List, Optional

from common.records import RecordId, decode, derived_id, row_values
from sqlalchemy import func, select

from backend.app.schemas.member_group import (
    MemberGroupDocument,
    MemberGroupMemberDocument,
    name_key,
)
from backend.app.repositories.postgres.form_access import AccessTargetNotFound
from backend.app.repositories.postgres.team_membership import (
    directory_pairs,
    team_member_pairs,
)
from backend.db.models import (
    MemberGroupMemberRow,
    MemberGroupRow,
    ScimGroupTeamLinkRow,
    WorkspaceUserRow,
)
from common.records.repository import RecordRepository


class TeamFull(Exception):
    """The team already holds the most members a team may."""


class TeamLimit(Exception):
    """The workspace already has the most teams it may."""


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

    async def create(self, group: MemberGroupDocument, max_teams: int) -> MemberGroupDocument:
        """Insert a new team unless the workspace already has ``max_teams``
        (``TeamLimit``); the count and the insert run under a lock of the
        workspace's teams, so two creations cannot both pass the limit. A
        second team with the same name is an ``IntegrityError``."""
        ws = _id(group.workspace_id)
        async with self._session() as session, session.begin():
            await session.execute(
                select(func.pg_advisory_xact_lock(func.hashtext("member_groups:" + ws)))
            )
            held = await session.execute(
                select(func.count())
                .select_from(MemberGroupRow)
                .where(MemberGroupRow.workspace_id == ws)
            )
            if held.scalar_one() >= max_teams:
                raise TeamLimit()
            group.touch()
            await session.execute(self._upsert_statement(row_values(group)))
        return group

    async def rename(
        self, workspace_id, group_id, name: str, description: Optional[str]
    ) -> Optional[MemberGroupDocument]:
        """Change a team's name and description under its row lock; ``None``
        when the team is gone (it is never created by this call)."""
        async with self._session() as session, session.begin():
            doc = (
                await session.execute(
                    select(MemberGroupRow.doc)
                    .where(
                        MemberGroupRow.workspace_id == _id(workspace_id),
                        MemberGroupRow.id == _id(group_id),
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                return None
            team = decode(MemberGroupDocument, doc)
            team.name = name
            # derived from the name, so rebuilt by hand: an assignment does not
            # run the model's validators
            team.name_key = name_key(name)
            team.description = description
            team.touch()
            await session.execute(self._upsert_statement(row_values(team)))
        return team

    async def delete(self, workspace_id, group_id) -> bool:
        """The team, its member rows and its directory links, in one transaction.
        Grants naming the team are the grant repository's to drop (the service
        does both)."""
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
                # the directory groups that fed the team are unlinked in the
                # same transaction (a link inserted meanwhile holds the team's
                # row lock, so it either lands before this delete and goes with
                # it, or finds the team gone)
                await self._delete_recorded(
                    session,
                    ScimGroupTeamLinkRow,
                    ScimGroupTeamLinkRow.workspace_id == _id(workspace_id),
                    ScimGroupTeamLinkRow.team_id == _id(group_id),
                )
        return bool(deleted)

    # -- members of a manual team ----------------------------------------------
    async def add_member(
        self, workspace_id, group_id, user_id, max_members: Optional[int] = None
    ) -> None:
        """Idempotent: the row id is derived from the pair.

        Refuses (``AccessTargetNotFound``) a team that is not this workspace's
        and a person who is not an active member of it (no membership, or a
        disabled one): whatever the caller checked before, the write itself
        keeps a team inside its workspace. ``TeamFull`` past ``max_members``."""
        ws, gid, uid = _id(workspace_id), _id(group_id), _id(user_id)
        async with self._session() as session, session.begin():
            # the team row is locked for the write (two adds cannot both pass the
            # size check) and the membership shared-locked (a removal at the same
            # moment waits, and its cleanup then removes this row)
            team = await session.execute(
                select(MemberGroupRow.id)
                .where(MemberGroupRow.workspace_id == ws, MemberGroupRow.id == gid)
                .limit(1)
                .with_for_update()
            )
            if team.first() is None:
                raise AccessTargetNotFound("group")
            member = await session.execute(
                select(WorkspaceUserRow.id)
                .where(
                    WorkspaceUserRow.workspace_id == ws,
                    WorkspaceUserRow.user_id == uid,
                    WorkspaceUserRow.disabled.is_not(True),
                )
                .limit(1)
                .with_for_update(read=True)
            )
            if member.first() is None:
                raise AccessTargetNotFound("member")
            document = MemberGroupMemberDocument(
                id=derived_id("member_group_member", gid, uid),
                group_id=RecordId(gid),
                workspace_id=RecordId(ws),
                user_id=uid,
            )
            if max_members is not None:
                held = await session.execute(
                    select(func.count())
                    .select_from(MemberGroupMemberRow)
                    .where(
                        MemberGroupMemberRow.workspace_id == ws,
                        MemberGroupMemberRow.group_id == gid,
                        MemberGroupMemberRow.user_id != uid,
                    )
                )
                if held.scalar_one() >= max_members:
                    raise TeamFull()
            await session.execute(
                self._upsert_statement(row_values(document), MemberGroupMemberRow)
            )

    async def remove_member(self, workspace_id, group_id, user_id) -> int:
        return await self.delete_where(
            MemberGroupMemberRow.workspace_id == _id(workspace_id),
            MemberGroupMemberRow.group_id == _id(group_id),
            MemberGroupMemberRow.user_id == _id(user_id),
            row=MemberGroupMemberRow,
        )

    async def manual_member_ids(self, workspace_id, group_id) -> List[str]:
        """The people listed in the team by hand."""
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

    async def directory_member_ids(self, workspace_id, group_id) -> List[str]:
        """The people in the team through a linked directory group (read now)."""
        async with self._session() as session:
            rows = await session.execute(
                directory_pairs(workspace_id, [group_id]).order_by("user_id")
            )
        return [str(user) for _, user in rows.all()]

    async def member_ids(self, workspace_id, group_id) -> List[str]:
        """Everyone in the team: those listed by hand, then those who are in it
        through a linked directory group (read now, never copied), each once."""
        listed = await self.manual_member_ids(workspace_id, group_id)
        async with self._session() as session:
            rows = await session.execute(
                directory_pairs(workspace_id, [group_id]).order_by("user_id")
            )
        everyone = list(listed)
        seen = set(listed)
        for _, user in rows.all():
            if str(user) not in seen:
                seen.add(str(user))
                everyone.append(str(user))
        return everyone

    async def group_ids_of(self, workspace_id, user_id) -> List[str]:
        """The teams of the workspace ``user_id`` is a member of (by hand or
        through a linked directory group)."""
        pairs = team_member_pairs(workspace_id, user_id=user_id)
        async with self._session() as session:
            rows = await session.execute(select(pairs.c.group_id))
        return [str(group) for group in rows.scalars().all()]

    # -- counts and cleanup ------------------------------------------------------
    async def count_in_workspace(self, workspace_id) -> int:
        return await self.count(MemberGroupRow.workspace_id == _id(workspace_id))

    async def names_of(self, workspace_id, group_ids: Iterable) -> Dict[str, str]:
        """The names of the given teams that belong to this workspace (one
        query; a deleted team, or one of another workspace, is not in it)."""
        ids = [_id(g) for g in dict.fromkeys(group_ids) if g]
        if not ids:
            return {}
        async with self._session() as session:
            rows = await session.execute(
                select(MemberGroupRow.id, MemberGroupRow.doc["name"].astext)
                .where(
                    MemberGroupRow.workspace_id == _id(workspace_id),
                    MemberGroupRow.id.in_(ids),
                )
            )
        return {str(i): name for i, name in rows.all() if name}

    async def member_counts(self, workspace_id) -> Dict[str, int]:
        """The number of people in each team of the workspace (by hand or
        through a linked directory group; a person in both counts once)."""
        pairs = team_member_pairs(workspace_id)
        async with self._session() as session:
            rows = await session.execute(
                select(pairs.c.group_id, func.count()).group_by(pairs.c.group_id)
            )
        return {str(group): int(total) for group, total in rows.all()}

    async def count_memberships(self, workspace_id, user_id) -> int:
        return await self.count_rows(
            MemberGroupMemberRow.workspace_id == _id(workspace_id),
            MemberGroupMemberRow.user_id == _id(user_id),
        )

    async def count_rows(self, *where) -> int:
        async with self._session() as session:
            return (
                await session.execute(
                    select(func.count()).select_from(MemberGroupMemberRow).where(*where)
                )
            ).scalar_one()

    async def remove_user(self, workspace_id, user_id) -> int:
        """The person leaves every team of the workspace."""
        return await self.delete_where(
            MemberGroupMemberRow.workspace_id == _id(workspace_id),
            MemberGroupMemberRow.user_id == _id(user_id),
            row=MemberGroupMemberRow,
        )

    async def remove_user_everywhere(self, user_id) -> Dict[str, int]:
        """The person leaves every team of every workspace (their account is
        gone): the number of teams left, per workspace."""
        async with self._session() as session:
            found = await session.execute(
                select(MemberGroupMemberRow.workspace_id).where(
                    MemberGroupMemberRow.user_id == _id(user_id)
                )
            )
        per_workspace: Dict[str, int] = {}
        for workspace in found.scalars().all():
            per_workspace[str(workspace)] = per_workspace.get(str(workspace), 0) + 1
        await self.delete_where(
            MemberGroupMemberRow.user_id == _id(user_id), row=MemberGroupMemberRow
        )
        return per_workspace

    async def delete_for_workspaces(self, workspace_ids: Iterable) -> int:
        """Every team and membership of these workspaces (they are gone)."""
        ids = [_id(w) for w in workspace_ids]
        if not ids:
            return 0
        await self.delete_where(
            MemberGroupMemberRow.workspace_id.in_(ids), row=MemberGroupMemberRow
        )
        await self.delete_where(
            ScimGroupTeamLinkRow.workspace_id.in_(ids), row=ScimGroupTeamLinkRow
        )
        return await self.delete_where(MemberGroupRow.workspace_id.in_(ids))
