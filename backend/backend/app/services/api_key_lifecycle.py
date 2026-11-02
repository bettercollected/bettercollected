"""What happens to a person's API keys when they leave: removed from a
workspace, their account deleted, deprovisioned by the directory.

A key acts as the person who created it (``created_by``). Their membership
going away makes the key refuse (403), but nothing made it stay dead: invited
again, or provisioned again by the directory, the same person got every old key
back under whatever role they now hold. So the keys are **revoked** when the
person leaves, in every path that ends or suspends a membership. The rows
stay (revoked, not deleted), so the audit and "last used" remain.

Each revoked key gets an ``api_key_revoked`` entry in the workspace's audit log
**before** the change (key id, reason, the person: ids and enum values only,
never a key's name, prefix or token).

* A member removal writes the entries here and revokes inside its own
  transaction (:mod:`backend.app.repositories.postgres.member_removal`), and is
  refused (503 ``audit_unavailable``) when an entry cannot be stored.
* Account deletion and directory deprovisioning revoke whatever the audit says:
  the entry is best effort (logged by id when it cannot be stored). Holding a
  deprovisioning or an erasure back because the log is down would leave the
  person's access in place, the worse direction.
"""

from __future__ import annotations

from typing import Iterable, List, Set, Tuple

from backend.app.repositories.postgres.identity import (
    PostgresWorkspaceAPIKeyRepository,
)
from backend.app.schemas.workspace_audit_event import (
    API_KEY_REVOKED,
    REVOKED_ACCOUNT_DELETED,
)
from backend.app.services.form_access import audit

__all__ = ["ApiKeyLifecycle", "SystemActor"]


class SystemActor:
    """The actor of an entry nobody asked for in a session: the directory
    sync, or the account that is being deleted."""

    sid = None

    def __init__(self, actor_id):
        self.id = str(actor_id)


class ApiKeyLifecycle:
    def __init__(self, api_key_repo: PostgresWorkspaceAPIKeyRepository, audit_repo):
        self._keys = api_key_repo
        self._audit = audit_repo

    async def _record(self, key_id, workspace_id, actor, user_id, reason, refuse):
        write = audit.record_or_refuse if refuse else audit.record
        await write(
            self._audit,
            API_KEY_REVOKED,
            workspace_id,
            actor,
            key_id=str(key_id),
            target_user_id=str(user_id),
            reason=reason,
        )

    # -- a member removal -----------------------------------------------------
    async def record_member_keys(
        self, workspace_id, user_id, actor, reason: str
    ) -> Set[str]:
        """Before the removal: one entry per live key the person created here;
        refuses the removal when one cannot be stored. Returns their ids."""
        recorded: Set[str] = set()
        for key_id, _ws in await self._keys.live_created_by(user_id, workspace_id):
            await self._record(key_id, workspace_id, actor, user_id, reason, True)
            recorded.add(key_id)
        return recorded

    async def record_late_keys(
        self,
        workspace_id,
        user_id,
        actor,
        reason: str,
        revoked: Iterable[str],
        recorded: Set[str],
    ) -> None:
        """A key the person made between the look and the removal was revoked
        too: its entry is written after the fact (the removal is done)."""
        for key_id in sorted(set(revoked) - recorded):
            await self._record(key_id, workspace_id, actor, user_id, reason, False)

    # -- a directory deprovisioning -------------------------------------------
    async def revoke_member_keys(
        self, workspace_id, user_id, actor, reason: str
    ) -> int:
        """Revoke the live keys the person created in this workspace, an entry
        each first. Returns how many were revoked."""
        for key_id, _ws in await self._keys.live_created_by(user_id, workspace_id):
            await self._record(key_id, workspace_id, actor, user_id, reason, False)
        return len(await self._keys.revoke_created_by(user_id, workspace_id))

    # -- an account deletion ---------------------------------------------------
    async def revoke_account_keys(
        self, user_id, going_workspaces: Iterable = ()
    ) -> int:
        """Revoke the live keys the person created in every workspace, an entry
        first in each workspace that stays. A workspace that is being deleted
        with the account gets no entry (nothing would read it). Returns how
        many were revoked."""
        going = {str(w) for w in going_workspaces}
        actor = SystemActor(user_id)
        live: List[Tuple[str, str]] = await self._keys.live_created_by(user_id)
        for key_id, workspace_id in live:
            if workspace_id not in going:
                await self._record(
                    key_id,
                    workspace_id,
                    actor,
                    user_id,
                    REVOKED_ACCOUNT_DELETED,
                    False,
                )
        return len(await self._keys.revoke_created_by(user_id))
