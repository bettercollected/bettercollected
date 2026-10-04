"""Applying a SCIM directory to its workspace (docs/sso.md, "Directory sync").

The same rules run for a webhook event and for a resync:

- **Users** (``apply_user``): only addresses on one of *this* workspace's
  verified SSO domains are provisioned; others are recorded as failed
  (``unverified_domain``). An active user gets the account (found, or created
  like a first SSO sign-in) and a membership (``provisioned_by="scim"``) with
  the role their groups map to, else the workspace's default SSO role, within
  the seat cap (``seat_limit`` otherwise; no account is created then). A
  deactivated or deleted user's membership is **disabled** (never deleted:
  their forms stay with the workspace) and their sessions revoked. The owner
  is never touched (``owner_protected``), nor is a member invited by hand
  (``manual_member``); a just-in-time SSO membership is taken over.
- **Groups**: the IdP's groups and who is in them; each group maps to at most
  one workspace role; the highest role among a user's groups wins.
- **Authoritative**: while the workspace has a directory, an SSO sign-in of a
  user it deactivated or deleted is refused (``is_deprovisioned``).

Nothing here logs an email or a name: only ids, codes and counts.
"""

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from beanie import PydanticObjectId
from common.db.beanie_bridge import derived_object_id
from common.exceptions.http import HTTPException as CommonHTTPException
from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.models.enum.workspace_roles import (
    WorkspaceRoles,
    canonical_role,
    canonical_roles,
    stored_role,
)
from backend.app.repositories.scim_repository import (
    ScimDirectoryRepository,
    ScimGroupMemberRepository,
    ScimGroupRepository,
    ScimUserRepository,
)
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository
from backend.app.schemas.workspace_user import DISABLED_BY_DIRECTORY
from backend.app.schemas.scim import (
    ScimDirectoryDocument,
    ScimGroupDocument,
    ScimGroupMemberDocument,
    ScimUserDocument,
    ScimUserState,
)
from backend.app.services.internal_auth import auth_service_headers
from backend.app.services.scim.roles import highest_role
from backend.app.services.session_service import RevokeReason, SessionService
from backend.app.services.sso.policy import default_sso_role
from backend.app.services.workspace_domain_service import WorkspaceDomainService
from backend.app.services.workspace_user_service import (
    PROVISIONED_BY_SCIM,
    PROVISIONED_BY_SSO,
    SeatLimitReached,
    WorkspaceUserService,
)
from backend.config import settings

# Why a directory user is ignored or failed; the admin page explains each.
REASON_MESSAGES: Dict[str, str] = {
    "unverified_domain": "The email address is not on one of this workspace's "
    "verified domains.",
    "seat_limit": "The workspace has no free seat. Free a seat or raise the "
    "limit, then resync.",
    "owner_protected": "This is the workspace owner, whom the directory never "
    "changes.",
    "manual_member": "This member was invited by hand; the directory does not "
    "manage them.",
    "account_conflict": "Several accounts use this email address (differing "
    "only in case). Contact support.",
    "workspace_unavailable": "The workspace is disabled.",
    "invalid_email": "The directory sent no usable email address.",
    "auth_unavailable": "The account service could not be reached; it is "
    "retried on the next change or resync.",
    "pending": "Not applied yet; it is retried on the next change or resync.",
}

# memberships the directory may manage: its own and just-in-time SSO ones
MANAGEABLE = (PROVISIONED_BY_SCIM, PROVISIONED_BY_SSO)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _email(value: Any) -> str:
    email = (str(value or "")).strip().lower()
    if "@" not in email or len(email) > 320 or " " in email:
        return ""
    return email


@dataclass
class DirectoryUser:
    """A user as Polis sends it (an event's ``data`` or a dsync listing)."""

    polis_user_id: str
    email: str
    active: bool
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    @classmethod
    def of(cls, data: Dict[str, Any]) -> Optional["DirectoryUser"]:
        polis_user_id = str(data.get("id") or "").strip()
        if not polis_user_id or len(polis_user_id) > 200:
            return None
        active = data.get("active", True)
        return cls(
            polis_user_id=polis_user_id,
            email=_email(data.get("email")),
            active=active is not False and str(active).lower() != "false",
            first_name=(str(data.get("first_name") or "")[:100] or None),
            last_name=(str(data.get("last_name") or "")[:100] or None),
        )


@dataclass
class SyncCounts:
    users: int = 0
    groups: int = 0
    provisioned: int = 0
    deprovisioned: int = 0
    failed: int = 0
    ignored: int = 0
    removed: int = 0
    # users not applied because the auth service was unavailable
    skipped: int = 0
    changes: List[str] = field(default_factory=list)

    def summary(self) -> Dict[str, int]:
        return {
            "users": self.users,
            "groups": self.groups,
            "provisioned": self.provisioned,
            "deprovisioned": self.deprovisioned,
            "failed": self.failed,
            "ignored": self.ignored,
            "removed": self.removed,
            "skipped": self.skipped,
        }


class AuthUnavailable(Exception):
    """The auth service could not be asked. Nothing is decided about the
    user: a webhook answers 503 (Polis retries), a resync skips the user and
    records the failure."""


class ReconcileRefused(Exception):
    """A resync would deprovision too many members at once (or Polis listed
    nobody): nothing was applied. ``force`` overrides it."""

    def __init__(self, would_deprovision: int, provisioned: int, listed: int):
        super().__init__("mass_deprovision_refused")
        self.would_deprovision = would_deprovision
        self.provisioned = provisioned
        self.listed = listed


class ScimSyncService:
    def __init__(
        self,
        directory_repo: ScimDirectoryRepository,
        user_repo: ScimUserRepository,
        group_repo: ScimGroupRepository,
        member_repo: ScimGroupMemberRepository,
        workspace_repo: WorkspaceRepository,
        workspace_user_repo: WorkspaceUserRepository,
        workspace_user_service: WorkspaceUserService,
        domain_service: WorkspaceDomainService,
        session_service: SessionService,
        http_client,
    ):
        self._directories = directory_repo
        self._users = user_repo
        self._groups = group_repo
        self._members = member_repo
        self._workspace_repo = workspace_repo
        self._workspace_users = workspace_user_repo
        self._workspace_user_service = workspace_user_service
        self._domains = domain_service
        self._sessions = session_service
        self._http = http_client

    # -- the auth service -----------------------------------------------------
    async def _account(self, user: DirectoryUser, create: bool):
        """(account id or None, conflict)."""
        try:
            reply = await self._http.post(
                settings.auth_settings.BASE_URL + "/auth/sso/directory-account",
                json={
                    "email": user.email,
                    "create": create,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
                headers=auth_service_headers(),
            )
        except (HTTPException, CommonHTTPException) as error:
            logger.warning(
                "SCIM: the auth service refused an account lookup (HTTP {})",
                getattr(error, "status_code", "?"),
            )
            raise AuthUnavailable()
        except Exception as error:  # noqa: BLE001 — unreachable
            logger.warning("SCIM: auth unreachable: {}", type(error).__name__)
            raise AuthUnavailable()
        reply = reply if isinstance(reply, dict) else {}
        if reply.get("conflict"):
            return None, True
        account = reply.get("user") or None
        account_id = (account or {}).get("id") or (account or {}).get("_id")
        return (str(account_id) if account_id else None), False

    # -- records --------------------------------------------------------------
    async def user_record(
        self, directory: ScimDirectoryDocument, user: DirectoryUser
    ) -> ScimUserDocument:
        """The stored record for ``user``: by Polis id; else one left by a
        replaced directory with the same email; else a new one (its id
        derived from the directory and the Polis id, so two deliveries racing
        write the same record)."""
        record = await self._users.find(directory.id, user.polis_user_id)
        if record is not None:
            return record
        if user.email:
            for candidate in await self._users.find_by_email(
                directory.workspace_id, user.email
            ):
                if candidate.directory_id == directory.id and candidate.replaced:
                    candidate.polis_user_id = user.polis_user_id
                    candidate.replaced = False
                    return candidate
        # new: nothing decided yet (an id for group memberships)
        return ScimUserDocument(
            id=derived_object_id("scim_user", directory.id, user.polis_user_id),
            directory_id=directory.id,
            workspace_id=directory.workspace_id,
            polis_user_id=user.polis_user_id,
            email=user.email,
            active=user.active,
            state=ScimUserState.IGNORED,
            reason="pending",
        )

    async def group_record(
        self, directory: ScimDirectoryDocument, polis_group_id: str, name: str
    ) -> ScimGroupDocument:
        """By Polis id; else the one group a replaced directory (token
        rotation) left with the same name, mapping included. Several such
        groups with that name: none is matched, the new group starts
        unmapped and is flagged for the owner (a name is not proof enough to
        hand out a role, Admin least of all)."""
        record = await self._groups.find(directory.id, polis_group_id)
        if record is not None:
            return record
        candidates = [
            c
            for c in await self._groups.list_by_directory(directory.id)
            if c.replaced and c.name == name
        ]
        if len(candidates) == 1:
            candidate = candidates[0]
            candidate.polis_group_id = polis_group_id
            candidate.replaced = False
            return candidate
        return ScimGroupDocument(
            id=derived_object_id("scim_group", directory.id, polis_group_id),
            directory_id=directory.id,
            workspace_id=directory.workspace_id,
            polis_group_id=polis_group_id,
            name=name,
            needs_review="duplicate_name" if candidates else None,
        )

    # -- users ----------------------------------------------------------------
    async def apply_user(
        self,
        directory: ScimDirectoryDocument,
        user: DirectoryUser,
        deleted: bool = False,
        workspace=None,
    ) -> ScimUserDocument:
        """Apply one directory user. Raises AuthUnavailable without changing
        the record's outcome when the auth service can't be asked."""
        workspace = workspace or await self._workspace_repo.find_by_id(
            directory.workspace_id
        )
        record = await self.user_record(directory, user)
        if (
            record.user_id
            and record.email
            and user.email
            and record.email != user.email
        ):
            # the IdP changed the address: the old account stops being this
            # directory user
            await self._disable_account(workspace, record.user_id, record.email)
            record.user_id = None
        email = user.email or record.email
        active = user.active and not deleted
        target = DirectoryUser(
            polis_user_id=user.polis_user_id,
            email=email,
            active=active,
            first_name=user.first_name,
            last_name=user.last_name,
        )
        if active:
            await self._provision(record, target, workspace)
        else:
            await self._deprovision(record, target, workspace)
        # only now, once decided, is the change recorded
        record.email = email
        record.active = active
        record.deleted = deleted
        record.last_event_at = _now()
        record.updated_at = _now()
        await self._users.save(record)
        if deleted:
            await self._members.delete_by_user(record.id)
        logger.info(
            "SCIM user {} of directory {}: {}{}",
            record.id,
            directory.id,
            record.state.value,
            f" ({record.reason})" if record.reason else "",
        )
        return record

    @staticmethod
    def _mark(record: ScimUserDocument, state: ScimUserState, reason=None) -> None:
        record.state = state
        record.reason = reason

    async def _on_this_workspaces_domain(self, workspace, email: str) -> bool:
        if not email:
            return False
        claim = await self._domains.sso_domain_claim(email)
        return claim is not None and str(claim.workspace_id) == str(workspace.id)

    async def _lift_directory_disable(self, membership, workspace) -> bool:
        """Re-enable what the directory disabled, nothing else (a plan
        downgrade's disable stays). False when it would take a seat and none
        is free (a disabled membership holds none)."""
        if DISABLED_BY_DIRECTORY not in membership.disabled_reasons:
            return True
        if membership.disabled_reasons == [
            DISABLED_BY_DIRECTORY
        ] and not await self._workspace_user_service.has_free_seat(workspace.id):
            return False
        membership.enable_for(DISABLED_BY_DIRECTORY)
        membership.updated_at = _now()
        await self._workspace_users.save(membership)
        return True

    async def _provision(self, record, user: DirectoryUser, workspace) -> None:
        if workspace is None or workspace.disabled:
            return self._mark(record, ScimUserState.FAILED, "workspace_unavailable")
        if not user.email:
            return self._mark(record, ScimUserState.FAILED, "invalid_email")
        if not await self._on_this_workspaces_domain(workspace, user.email):
            return self._mark(record, ScimUserState.FAILED, "unverified_domain")
        account_id, conflict = await self._account(user, create=False)
        if conflict:
            return self._mark(record, ScimUserState.FAILED, "account_conflict")
        if account_id and account_id == str(workspace.owner_id):
            record.user_id = account_id
            return self._mark(record, ScimUserState.IGNORED, "owner_protected")
        membership = (
            await self._workspace_user_service.find_member(workspace.id, account_id)
            if account_id
            else None
        )
        if membership is not None:
            record.user_id = account_id
            if membership.provisioned_by not in MANAGEABLE:
                # invited by hand: the directory never sets its role; it only
                # lifts its own deactivation
                if not await self._lift_directory_disable(membership, workspace):
                    return self._mark(record, ScimUserState.FAILED, "seat_limit")
                return self._mark(record, ScimUserState.IGNORED, "manual_member")
            if not await self._lift_directory_disable(membership, workspace):
                return self._mark(record, ScimUserState.FAILED, "seat_limit")
            role = await self.role_for(record, workspace)
            if membership.provisioned_by != PROVISIONED_BY_SCIM or canonical_roles(
                membership.roles
            ) != [role.value]:
                membership.provisioned_by = PROVISIONED_BY_SCIM
                membership.roles = [stored_role(role)]
                membership.updated_at = _now()
                await self._workspace_users.save(membership)
            return self._mark(record, ScimUserState.PROVISIONED)
        # a new member: the seat cap first, before any account exists
        if not await self._workspace_user_service.has_free_seat(workspace.id):
            return self._mark(record, ScimUserState.FAILED, "seat_limit")
        if account_id is None:
            account_id, conflict = await self._account(user, create=True)
            if conflict or not account_id:
                return self._mark(record, ScimUserState.FAILED, "account_conflict")
        record.user_id = account_id
        role = await self.role_for(record, workspace)
        try:
            await self._workspace_user_service.add_directory_member(
                workspace.id, account_id, role
            )
        except SeatLimitReached:
            return self._mark(record, ScimUserState.FAILED, "seat_limit")
        return self._mark(record, ScimUserState.PROVISIONED)

    async def _deprovision(self, record, user: DirectoryUser, workspace) -> None:
        account_id = record.user_id
        if account_id is None and user.email:
            account_id, _conflict = await self._account(user, create=False)
        record.user_id = account_id
        if workspace is not None and account_id == str(workspace.owner_id):
            return self._mark(record, ScimUserState.IGNORED, "owner_protected")
        if workspace is not None and account_id:
            outcome = await self._disable_account(workspace, account_id, user.email)
            if outcome == "manual_off_domain":
                return self._mark(record, ScimUserState.IGNORED, "manual_member")
        return self._mark(record, ScimUserState.DEPROVISIONED)

    async def _disable_account(self, workspace, account_id: str, email: str) -> str:
        """Disable the account's membership (reason ``directory``) and end
        all of its sessions. Never the owner's. A membership invited by hand
        too, when the address is on this workspace's verified domains (the
        directory speaks for those). Never deletes anything."""
        if workspace is None or account_id == str(workspace.owner_id):
            return "owner"
        membership = await self._workspace_user_service.find_member(
            workspace.id, account_id
        )
        if membership is None:
            return "none"
        managed = membership.provisioned_by in MANAGEABLE
        if not managed and not await self._on_this_workspaces_domain(workspace, email):
            return "manual_off_domain"
        changed = membership.disable_for(DISABLED_BY_DIRECTORY)
        if managed and membership.provisioned_by != PROVISIONED_BY_SCIM:
            membership.provisioned_by = PROVISIONED_BY_SCIM
            changed = True
        if changed:
            membership.updated_at = _now()
            await self._workspace_users.save(membership)
        # every session of the account, its other workspaces' included: the
        # simplest safe choice (docs/sso.md); its other memberships stay
        revoked = await self._sessions.revoke_all_for_user(
            account_id, RevokeReason.SCIM_DEPROVISIONED
        )
        logger.info(
            "SCIM: membership of user {} in workspace {} disabled, {} sessions revoked",
            account_id,
            workspace.id,
            revoked,
        )
        return "disabled"

    # -- roles ----------------------------------------------------------------
    async def role_for(self, record: ScimUserDocument, workspace) -> WorkspaceRoles:
        """The highest role among the user's mapped groups, else the
        workspace's default SSO role."""
        roles = []
        for link in await self._members.list_by_user(record.id):
            group = await self._groups.get(link.group_id)
            if group is not None and group.role:
                roles.append(group.role)
        best = highest_role(roles)
        if best:
            return WorkspaceRoles(best)
        return canonical_role(default_sso_role(workspace)) or WorkspaceRoles.VIEWER

    async def recompute(self, records: Iterable[ScimUserDocument], workspace) -> int:
        """Apply the role the groups now give to provisioned users whose
        membership the directory manages. Returns how many changed."""
        changed = 0
        if workspace is None or workspace.disabled:
            return 0
        for record in records:
            if record.state != ScimUserState.PROVISIONED or not record.user_id:
                continue
            if record.user_id == str(workspace.owner_id):
                continue
            membership = await self._workspace_user_service.find_member(
                workspace.id, record.user_id
            )
            if membership is None or membership.provisioned_by != PROVISIONED_BY_SCIM:
                continue
            role = await self.role_for(record, workspace)
            if canonical_roles(membership.roles) != [role.value]:
                membership.roles = [stored_role(role)]
                membership.updated_at = _now()
                await self._workspace_users.save(membership)
                changed += 1
                logger.info(
                    "SCIM: role of user {} in workspace {} is now {}",
                    record.user_id,
                    workspace.id,
                    role.value,
                )
        return changed

    async def recompute_workspace(self, workspace) -> int:
        """The workspace's default SSO role changed: members without a mapped
        group follow it."""
        if workspace is None:
            return 0
        directory = await self._directories.find_by_workspace(workspace.id)
        if directory is None:
            return 0
        return await self.recompute(
            await self._users.list_by_directory(directory.id), workspace
        )

    async def recompute_group(self, group: ScimGroupDocument, workspace=None) -> int:
        workspace = workspace or await self._workspace_repo.find_by_id(
            group.workspace_id
        )
        links = await self._members.list_by_group(group.id)
        records = await self._users.list_by_ids([link.scim_user_id for link in links])
        return await self.recompute(records, workspace)

    # -- groups ---------------------------------------------------------------
    async def apply_group(
        self, directory: ScimDirectoryDocument, data: Dict[str, Any]
    ) -> Optional[ScimGroupDocument]:
        polis_group_id = str(data.get("id") or "").strip()
        if not polis_group_id or len(polis_group_id) > 200:
            return None
        name = str(data.get("name") or "").strip()[:200] or polis_group_id
        group = await self.group_record(directory, polis_group_id, name)
        group.name = name
        group.updated_at = _now()
        await self._groups.save(group)
        return group

    async def delete_group(
        self, directory: ScimDirectoryDocument, polis_group_id: str
    ) -> int:
        group = await self._groups.find(directory.id, polis_group_id)
        if group is None:
            return 0
        links = await self._members.list_by_group(group.id)
        records = await self._users.list_by_ids([link.scim_user_id for link in links])
        await self._members.delete_by_group(group.id)
        await self._groups.delete(group.id)
        workspace = await self._workspace_repo.find_by_id(directory.workspace_id)
        return await self.recompute(records, workspace)

    async def set_membership(
        self,
        directory: ScimDirectoryDocument,
        group_data: Dict[str, Any],
        user: DirectoryUser,
        member: bool,
    ) -> None:
        """``group.user_added`` / ``group.user_removed``: the event carries
        the user and the group."""
        group = await self.apply_group(directory, group_data)
        if group is None:
            return
        record = await self._users.find(directory.id, user.polis_user_id)
        if record is None:
            if not member:
                return
            # first time we hear of this user: provision them first
            record = await self.apply_user(directory, user)
        if member:
            await self._members.add(
                ScimGroupMemberDocument(
                    id=derived_object_id(group.id, record.id),
                    directory_id=directory.id,
                    group_id=group.id,
                    scim_user_id=record.id,
                )
            )
        else:
            await self._members.remove(group.id, record.id)
        workspace = await self._workspace_repo.find_by_id(directory.workspace_id)
        await self.recompute([record], workspace)

    # -- the SSO guard --------------------------------------------------------
    async def is_deprovisioned(self, workspace_id, email: str) -> bool:
        """Whether the workspace's directory deactivated or deleted
        ``email``: its SSO sign-in is then refused (SCIM is authoritative)."""
        email = _email(email)
        if not email:
            return False
        directory = await self._directories.find_by_workspace(
            PydanticObjectId(workspace_id)
        )
        if directory is None:
            return False
        records = [
            r
            for r in await self._users.find_by_email(directory.workspace_id, email)
            if r.directory_id == directory.id and not r.replaced
        ]
        if not records:
            return False
        # an active record wins (the same person re-created in the IdP)
        return not any(r.active and not r.deleted for r in records)

    # -- resync ---------------------------------------------------------------
    @staticmethod
    def in_rotation_grace(directory: ScimDirectoryDocument, now=None) -> bool:
        """Within ``SCIM_ROTATION_GRACE_HOURS`` of a token rotation: the
        identity provider may not have pushed everything to the new
        directory yet, so a resync removes nobody and no group."""
        if directory.rotated_at is None:
            return False
        now = now or _now()
        grace = dt.timedelta(hours=settings.scim.ROTATION_GRACE_HOURS)
        return now - directory.rotated_at < grace

    @staticmethod
    def check_mass_deprovision(
        existing: List[ScimUserDocument],
        parsed: List[DirectoryUser],
        in_grace: bool,
    ) -> None:
        """Refuse (ReconcileRefused) a resync that would deprovision more
        than ``SCIM_RECONCILE_MAX_DEPROVISION_RATIO`` of the provisioned
        members and at least ``SCIM_RECONCILE_MIN_DEPROVISION`` of them, or
        that got no user at all from Polis while members are provisioned: a
        half-broken listing must not empty the workspace overnight."""
        provisioned = [
            r
            for r in existing
            if r.state == ScimUserState.PROVISIONED and not r.deleted
        ]
        if not provisioned:
            return
        listed = {u.polis_user_id for u in parsed}
        active_ids = {u.polis_user_id for u in parsed if u.active}
        active_emails = {u.email for u in parsed if u.active and u.email}
        would = 0
        for record in provisioned:
            if record.polis_user_id in active_ids:
                continue
            if record.replaced and record.email in active_emails:
                continue
            if record.polis_user_id in listed or not in_grace:
                would += 1
        config = settings.scim
        if (not parsed and not in_grace) or (
            would >= config.RECONCILE_MIN_DEPROVISION
            and would > config.RECONCILE_MAX_DEPROVISION_RATIO * len(provisioned)
        ):
            raise ReconcileRefused(would, len(provisioned), len(parsed))

    async def reconcile(
        self,
        directory: ScimDirectoryDocument,
        users: List[Dict[str, Any]],
        groups: List[Tuple[Dict[str, Any], List[str]]],
        force: bool = False,
    ) -> SyncCounts:
        """Make the workspace match the directory as Polis holds it now:
        ``users`` and ``groups`` (each with its members' Polis user ids), as
        listed by Polis's dsync API. Catches events that never arrived.
        Raises ReconcileRefused before changing anything when it would
        deprovision too many (``force`` skips that check)."""
        counts = SyncCounts()
        workspace = await self._workspace_repo.find_by_id(directory.workspace_id)
        parsed = [u for u in (DirectoryUser.of(d) for d in users) if u is not None]
        counts.users = len(parsed)
        in_grace = self.in_rotation_grace(directory)
        if not force:
            self.check_mass_deprovision(
                await self._users.list_by_directory(directory.id), parsed, in_grace
            )
        # 1. a record for every user (so memberships can point at it)
        records: Dict[str, ScimUserDocument] = {}
        for user in parsed:
            record = await self.user_record(directory, user)
            await self._users.save(record)
            records[user.polis_user_id] = record
        # 2. groups and who is in them
        seen_groups = set()
        for data, member_ids in groups:
            group = await self.apply_group(directory, data)
            if group is None:
                continue
            seen_groups.add(group.id)
            counts.groups += 1
            wanted = {records[m].id for m in member_ids if m in records}
            current = {
                link.scim_user_id
                for link in await self._members.list_by_group(group.id)
            }
            for scim_user_id in wanted - current:
                await self._members.add(
                    ScimGroupMemberDocument(
                        id=derived_object_id(group.id, scim_user_id),
                        directory_id=directory.id,
                        group_id=group.id,
                        scim_user_id=scim_user_id,
                    )
                )
            for scim_user_id in current - wanted:
                await self._members.remove(group.id, scim_user_id)
        # groups Polis no longer has (not while a rotation's grace lasts: the
        # previous directory's groups keep their mapping until matched)
        for group in await self._groups.list_by_directory(directory.id):
            if group.id not in seen_groups and not (group.replaced and in_grace):
                await self._members.delete_by_group(group.id)
                await self._groups.delete(group.id)
        # 3. every user's membership, status and role
        for user in parsed:
            try:
                record = await self.apply_user(directory, user, workspace=workspace)
            except AuthUnavailable:
                counts.skipped += 1
                continue
            self._count(counts, record)
        # 4. users Polis no longer has: deleted in the directory (none while
        # a rotation's grace lasts)
        if in_grace:
            return counts
        listed = {r.id for r in records.values()}
        for record in await self._users.list_by_directory(directory.id):
            if record.id in listed or record.deleted:
                continue
            gone = DirectoryUser(
                polis_user_id=record.polis_user_id, email=record.email, active=False
            )
            try:
                await self.apply_user(
                    directory, gone, deleted=True, workspace=workspace
                )
            except AuthUnavailable:
                counts.skipped += 1
                continue
            counts.removed += 1
        return counts

    @staticmethod
    def _count(counts: SyncCounts, record: ScimUserDocument) -> None:
        if record.state == ScimUserState.PROVISIONED:
            counts.provisioned += 1
        elif record.state == ScimUserState.DEPROVISIONED:
            counts.deprovisioned += 1
        elif record.state == ScimUserState.FAILED:
            counts.failed += 1
        else:
            counts.ignored += 1
