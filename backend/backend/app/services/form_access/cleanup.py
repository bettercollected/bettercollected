"""What happens to grants and team memberships when what they name goes away
(the lifecycle table of the design: a form deleted, a team deleted, a member
removed, an account deleted, a workspace deleted).

Grants are keyed by ids with no foreign key, so every path that removes a form,
a team, a member or a workspace calls one of these. They run **whatever the
switch says**: stored grants stay while the switch is off, but a grant for a
form or a person that no longer exists must not linger and come back to life
(a re-invited member, a re-used id) when the switch is turned on.

They only delete; the callers that act for a person (member removal, team
deletion) write the audit entry first (``audit.record_or_refuse``).
"""

from __future__ import annotations

from typing import Callable, Dict, Iterable, Optional, Tuple

from backend.app.repositories.postgres.form_access import (
    PostgresFormAccessGrantRepository,
)
from backend.app.repositories.postgres.member_groups import (
    PostgresMemberGroupRepository,
)
from backend.app.schemas.form_access_grant import SUBJECT_GROUP, SUBJECT_USER
from backend.app.schemas.workspace_audit_event import ACCESS_MEMBER_PURGED
from backend.app.services.form_access import audit


class FormAccessCleanup:
    def __init__(
        self,
        grant_repo: PostgresFormAccessGrantRepository,
        group_repo: PostgresMemberGroupRepository,
        audit_repo=None,
        invalidate: Optional[Callable[[], None]] = None,
        scim_group_repo=None,
    ):
        self._grants = grant_repo
        self._groups = group_repo
        self._audit = audit_repo
        # the directory groups linked to a team (unlinked when the team goes)
        self._scim_groups = scim_group_repo
        # forgets what this request remembered of a form's access
        self._invalidate = invalidate or (lambda: None)

    def forget_memo(self) -> None:
        """Forget what this request remembered (a write was made elsewhere)."""
        self._invalidate()

    # -- a form --------------------------------------------------------------
    async def forget_form(self, workspace_id, form_id) -> int:
        """The form left this workspace (deleted, or unlinked from it): its
        grants here go."""
        removed = await self._grants.delete_for_form(workspace_id, form_id)
        self._invalidate()
        return removed

    async def forget_forms(self, form_ids: Iterable[str]) -> int:
        """These forms are gone from every workspace."""
        removed = await self._grants.delete_for_forms(form_ids)
        self._invalidate()
        return removed

    # -- a team --------------------------------------------------------------
    async def count_team_grants(self, workspace_id, group_id) -> int:
        return await self._grants.count_for_subject(
            workspace_id, SUBJECT_GROUP, group_id
        )

    async def forget_team(self, workspace_id, group_id) -> Tuple[int, bool]:
        """The team is deleted: its grants and its member rows go with it, and
        the directory groups linked to it are unlinked.
        Returns ``(grants removed, team existed)``."""
        # the team first: a failure after it leaves grants for a team that is
        # gone (inert: nobody is in it, and none can be added), never a team
        # that is still there without its grants
        existed = await self._groups.delete(workspace_id, group_id)
        if self._scim_groups is not None:
            # a link to a team that is gone resolves to nobody; clearing it
            # shows the group as unlinked again
            await self._scim_groups.unlink_team(workspace_id, group_id)
        removed = await self._grants.delete_for_subject(
            workspace_id, SUBJECT_GROUP, group_id
        )
        self._invalidate()
        return removed, existed

    # -- a member ------------------------------------------------------------
    async def count_member(self, workspace_id, user_id) -> int:
        """The grants and team memberships that removing this member removes."""
        return await self._grants.count_for_subject(
            workspace_id, SUBJECT_USER, user_id
        ) + await self._groups.count_memberships(workspace_id, user_id)

    async def forget_member(self, workspace_id, user_id) -> int:
        """The member left the workspace: their grants and teams here go (a
        person invited again starts with none). Returns how many rows."""
        grants = await self._grants.delete_for_subject(
            workspace_id, SUBJECT_USER, user_id
        )
        teams = await self._groups.remove_user(workspace_id, user_id)
        self._invalidate()
        return grants + teams

    async def forget_account(self, user_id, *, actor=None) -> Dict[str, int]:
        """The account is deleted: the person's grants and teams in every
        workspace go, and one entry per workspace says how many (best effort:
        deleting an account is never held up by its audit). Returns the rows
        removed per workspace."""
        per_workspace = dict(await self._grants.delete_user_everywhere(user_id))
        for workspace_id, teams in (
            await self._groups.remove_user_everywhere(user_id)
        ).items():
            per_workspace[workspace_id] = per_workspace.get(workspace_id, 0) + teams
        self._invalidate()
        for workspace_id, count in per_workspace.items():
            await audit.record(
                self._audit,
                ACCESS_MEMBER_PURGED,
                workspace_id,
                actor if actor is not None else _Account(user_id),
                target_user_id=str(user_id),
                count=count,
            )
        return per_workspace

    # -- a workspace ---------------------------------------------------------
    async def forget_workspaces(self, workspace_ids: Iterable) -> None:
        """These workspaces are deleted: every grant, team and membership in
        them goes."""
        ids = [str(w) for w in workspace_ids]
        await self._grants.delete_for_workspaces(ids)
        await self._groups.delete_for_workspaces(ids)
        self._invalidate()


class _Account:
    """The actor of an entry written for an account deletion: the account."""

    sid = None

    def __init__(self, user_id):
        self.id = str(user_id)
