"""Who is in a team: the members listed by hand, and the members of the
directory groups linked to it (rows of ``scim_group_team_links``).

The directory side is **read at call time** from the tables the directory sync
keeps (``scim_group_members`` -> ``scim_users``): nothing is copied into the
team. A deprovisioned person, a person removed from the group in the directory
or a group deleted there stops being in the team on the next query.

A person counts through a directory group only while all of these hold: their
directory record is active and not deleted, it points at their account, the
group is linked to a team of **this** workspace, and they are an active member
of this workspace (a disabled membership holds nothing). The workspace id is
matched on the directory record, on the team and on the membership, so a link
can never reach a team or a person of another workspace.
"""

from typing import Iterable, Optional

from sqlalchemy import and_, select, union

from backend.db.models import (
    MemberGroupMemberRow,
    MemberGroupRow,
    ScimGroupMemberRow,
    ScimGroupRow,
    ScimGroupTeamLinkRow,
    ScimUserRow,
    WorkspaceUserRow,
)

# the directory states of a record that may stand for a person in a team
# ("failed" and "deprovisioned" never do)
_LIVE_STATES = ("provisioned", "ignored")


def _id(value) -> str:
    return str(value)


def directory_pairs(workspace_id, team_ids: Optional[Iterable] = None, user_id=None):
    """``(group_id, user_id)`` of the people who are in a team through a linked
    directory group, in this workspace.

    A group or a user the directory replaced (a token rotation, until the new
    directory has matched them) still counts: the rotation's grace period exists
    so that nobody loses access while the new directory catches up, and a
    replaced group keeps its role mapping and its link the same way. When the
    new directory matches them, the same records carry on; when it does not,
    the records go at the next resync."""
    ws = _id(workspace_id)
    team = ScimGroupTeamLinkRow.team_id
    account = ScimUserRow.user_id
    statement = (
        select(team.label("group_id"), account.label("user_id"))
        .select_from(ScimGroupTeamLinkRow)
        .join(ScimGroupRow, ScimGroupRow.id == ScimGroupTeamLinkRow.group_id)
        .join(ScimGroupMemberRow, ScimGroupMemberRow.group_id == ScimGroupRow.id)
        .join(ScimUserRow, ScimUserRow.id == ScimGroupMemberRow.scim_user_id)
        .join(
            MemberGroupRow,
            and_(MemberGroupRow.id == team, MemberGroupRow.workspace_id == ws),
        )
        .join(
            WorkspaceUserRow,
            and_(
                WorkspaceUserRow.workspace_id == ws,
                WorkspaceUserRow.user_id == account,
                WorkspaceUserRow.disabled.is_not(True),
            ),
        )
        .where(
            ScimGroupTeamLinkRow.workspace_id == ws,
            ScimUserRow.workspace_id == ws,
            ScimUserRow.directory_id == ScimGroupRow.directory_id,
            ScimUserRow.doc["active"].astext == "true",
            ScimUserRow.doc["deleted"].astext.is_distinct_from("true"),
            ScimUserRow.doc["state"].astext.in_(_LIVE_STATES),
        )
    )
    if team_ids is not None:
        statement = statement.where(team.in_([_id(t) for t in team_ids]))
    if user_id is not None:
        statement = statement.where(account == _id(user_id))
    return statement


def _manual_pairs(workspace_id, team_ids: Optional[Iterable] = None, user_id=None):
    statement = select(
        MemberGroupMemberRow.group_id.label("group_id"),
        MemberGroupMemberRow.user_id.label("user_id"),
    ).where(MemberGroupMemberRow.workspace_id == _id(workspace_id))
    if team_ids is not None:
        statement = statement.where(
            MemberGroupMemberRow.group_id.in_([_id(t) for t in team_ids])
        )
    if user_id is not None:
        statement = statement.where(MemberGroupMemberRow.user_id == _id(user_id))
    return statement


def team_member_pairs(workspace_id, team_ids: Optional[Iterable] = None, user_id=None):
    """``(group_id, user_id)`` of every (team, person) of the workspace, manual
    or through a directory group, each pair once (a person in both is one row).
    ``team_ids`` / ``user_id`` narrow it."""
    return union(
        _manual_pairs(workspace_id, team_ids, user_id),
        directory_pairs(workspace_id, team_ids, user_id),
    ).subquery()


def teams_of_user(workspace_id, user_id):
    """A ``SELECT group_id`` of the teams ``user_id`` is in (manual or through a
    directory group), to use inside ``IN (...)``."""
    pairs = team_member_pairs(workspace_id, user_id=user_id)
    return select(pairs.c.group_id)
