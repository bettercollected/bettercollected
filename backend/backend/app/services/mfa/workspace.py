"""The workspace side of the authenticator-app second factor (docs/totp.md): the
"require an authenticator app for members" setting, who has set one up, and
removing a member's factor.

Who may do what:

* the setting and a member's reset: workspace owners only (like the single
  sign-on settings); reading the overview: owners and holders of
  ``security.manage``;
* a reset of a member's factor is only for a member whose address is on one of
  the workspace's verified domains, or who belongs to no other workspace (a
  factor is per account: an owner of one workspace must not be able to strip the
  protection of a person whose account reaches another workspace too);
* the platform administrator may reset anyone's, never their own.

Every change is audited with ids only; a reset ends the target's sessions and
mails the target.
"""

import datetime as dt
import logging
from http import HTTPStatus
from typing import List, Optional

from common.ids import RecordId
from fastapi_camelcase import CamelModel

from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.schemas.workspace_audit_event import (
    NO_WORKSPACE,
    TOTP_POLICY_CHANGED,
    TOTP_RESET,
    WorkspaceAuditEventDocument,
)
from backend.app.services.internal_auth import auth_service_headers
from backend.app.services.mfa import notifier as notifier_module
from backend.app.services.mfa.service import _refused, refuse_when_off, totp_enabled
from backend.app.services.session_service import RevokeReason
from backend.config import settings

log = logging.getLogger(__name__)


class TotpPolicyDto(CamelModel):
    """The workspace's second-factor setting and how far it is met."""

    # the instance has the feature on (TOTP_ENABLED)
    available: bool
    # members must present a second factor
    required: bool
    # active members, and how many of them have no authenticator app yet
    members: int = 0
    members_without_factor: int = 0


class SetTotpPolicyDto(CamelModel):
    required: bool


class RequirementLookup:
    """Whether a workspace an account belongs to requires a second factor (the
    account then cannot turn its own off)."""

    def __init__(self, workspace_repo, workspace_user_repo):
        self._workspaces = workspace_repo
        self._members = workspace_user_repo

    async def refuse_if_required(self, user_id: str) -> None:
        if not totp_enabled():
            return
        memberships = [
            m for m in await self._members.get_mine_workspaces(user_id) if not m.disabled
        ]
        if not memberships:
            return
        workspaces = await self._workspaces.get_workspace_by_ids(
            [m.workspace_id for m in memberships]
        )
        if any(w.require_totp and not w.disabled for w in workspaces):
            raise _refused(
                HTTPStatus.CONFLICT,
                "required_by_workspace",
                "A workspace you belong to requires an authenticator app, so it "
                "cannot be turned off.",
            )


class WorkspaceTotpService:
    def __init__(
        self,
        workspace_repo,
        workspace_user_repo,
        factor_repo,
        authorization_service,
        session_service,
        domain_repo,
        http_client,
        audit_repo=None,
        notifier=None,
    ):
        self._workspaces = workspace_repo
        self._members = workspace_user_repo
        self._factors = factor_repo
        self._authorization = authorization_service
        self._sessions = session_service
        self._domains = domain_repo
        self._http_client = http_client
        self._audit = audit_repo
        self._notifier = notifier

    # -- the setting -----------------------------------------------------------
    async def overview(self, workspace_id: RecordId, user) -> TotpPolicyDto:
        await self._authorization.authorize(
            user, Permission.SECURITY_MANAGE, workspace_id
        )
        workspace = await self._workspaces.get_or_404(workspace_id)
        return await self._overview(workspace)

    async def _overview(self, workspace) -> TotpPolicyDto:
        if not totp_enabled():
            return TotpPolicyDto(
                available=False, required=bool(workspace.require_totp)
            )
        active = [
            str(m.user_id)
            for m in await self._members.get_workspace_users(workspace.id)
            if not m.disabled
        ]
        with_factor = await self._factors.users_with_factor(active)
        return TotpPolicyDto(
            available=True,
            required=bool(workspace.require_totp),
            members=len(active),
            members_without_factor=len([u for u in active if u not in with_factor]),
        )

    async def set_required(
        self, workspace_id: RecordId, user, required: bool
    ) -> TotpPolicyDto:
        """Turn the setting on or off. Owners only. Turning it on needs the
        owner's own session to hold a second factor (else 409 ``enrol_first``),
        so the owner cannot lock themselves out."""
        refuse_when_off()
        await self._authorization.require_owner(user, workspace_id)
        workspace = await self._workspaces.get_or_404(workspace_id)
        if required and not getattr(user, "mfa", None):
            raise _refused(
                HTTPStatus.CONFLICT,
                "enrol_first",
                "Set up your own authenticator app, and enter its code in this "
                "session, before requiring one.",
            )
        if bool(workspace.require_totp) != required:
            await self._workspaces.set_fields(
                workspace,
                {"require_totp": required, "updated_at": dt.datetime.now(dt.timezone.utc)},
            )
            await self._record(TOTP_POLICY_CHANGED, workspace.id, user.id, user.sid)
            log.info(
                "second-factor policy of workspace %s set to %s by %s",
                workspace.id,
                required,
                user.id,
            )
        return await self._overview(workspace)

    # -- reset -----------------------------------------------------------------
    async def reset_member(self, workspace_id: RecordId, user, target_id: str) -> None:
        """An owner removes a member's factor (see the module notes for who)."""
        refuse_when_off()
        await self._authorization.require_owner(user, workspace_id)
        if str(target_id) == str(user.id):
            raise _refused(
                HTTPStatus.CONFLICT,
                "reset_self",
                "Turn off your own authenticator app in your account settings.",
            )
        workspace = await self._workspaces.get_or_404(workspace_id)
        membership = await self._members.find_workspace_user(workspace_id, target_id)
        if membership is None:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Not a member of this workspace.")
        if not await self._may_reset(workspace, target_id):
            raise _refused(
                HTTPStatus.CONFLICT,
                "reset_not_allowed",
                "This person's account is also used outside this workspace. They "
                "can sign in with a recovery code, or ask the administrator of "
                "this service.",
            )
        if not await self._factors.confirmed(target_id):
            raise HTTPException(HTTPStatus.NOT_FOUND, "No authenticator app is set up.")
        await self._remove(target_id, workspace.id, user)
        self._tell(
            target_id,
            notifier_module.RESET_OWNER,
            workspace_title=getattr(workspace, "title", None)
            or getattr(workspace, "workspace_name", None),
        )

    async def admin_reset(self, user, target_id: str) -> None:
        """The platform administrator removes anyone's factor (never their own)."""
        refuse_when_off()
        if str(target_id) == str(user.id):
            raise _refused(
                HTTPStatus.CONFLICT,
                "reset_self",
                "Turn off your own authenticator app in your account settings.",
            )
        if not await self._factors.confirmed(target_id):
            raise HTTPException(HTTPStatus.NOT_FOUND, "No authenticator app is set up.")
        await self._remove(target_id, RecordId(NO_WORKSPACE), user)
        self._tell(target_id, notifier_module.RESET)

    async def _remove(self, target_id: str, workspace_id, actor) -> None:
        await self._factors.delete_for_user(str(target_id))
        await self._sessions.revoke_all_for_user(
            str(target_id), RevokeReason.MFA_RESET
        )
        await self._record(
            TOTP_RESET, workspace_id, actor.id, actor.sid, target_user_id=target_id
        )

    async def _may_reset(self, workspace, target_id: str) -> bool:
        """The member's address is on a verified domain of this workspace, or
        they belong to no other workspace."""
        others = [
            m
            for m in await self._members.get_mine_workspaces(target_id)
            if str(m.workspace_id) != str(workspace.id)
        ]
        if not others:
            return True
        email = await self._email_of(target_id)
        domain = email.rpartition("@")[2].lower() if email and "@" in email else None
        if not domain:
            return False
        claim = await self._domains.find_verified(domain)
        return claim is not None and str(claim.workspace_id) == str(workspace.id)

    async def _email_of(self, user_id: str) -> Optional[str]:
        try:
            reply = await self._http_client.get(
                settings.auth_settings.BASE_URL + "/users",
                params={"user_ids": [user_id]},
                headers=auth_service_headers(),
                timeout=10,
            )
        except Exception as error:  # noqa: BLE001 — no address: not allowed
            log.warning("member address lookup failed (%s)", type(error).__name__)
            return None
        for info in (reply or {}).get("users_info") or []:
            if str(info.get("_id") or info.get("id") or "") == str(user_id):
                return info.get("email")
        return None

    # -- the member list -------------------------------------------------------
    async def flags(self, user_ids: List[str]) -> Optional[set]:
        """Which of ``user_ids`` have an authenticator app; None while the
        feature is off (the member list then shows no column)."""
        if not totp_enabled():
            return None
        return await self._factors.users_with_factor([str(u) for u in user_ids])

    # -- helpers ---------------------------------------------------------------
    def _tell(self, user_id, kind: str, **extra) -> None:
        if self._notifier is not None:
            self._notifier.notify(user_id, kind, **extra)

    async def _record(
        self, event: str, workspace_id, actor_id, session_id, target_user_id=None
    ) -> None:
        if self._audit is None:
            return
        try:
            await self._audit.record(
                WorkspaceAuditEventDocument(
                    id=RecordId(),
                    workspace_id=RecordId(str(workspace_id)),
                    user_id=str(actor_id),
                    session_id=str(session_id) if session_id else None,
                    event=event,
                    target_user_id=str(target_user_id) if target_user_id else None,
                )
            )
        except Exception as error:  # noqa: BLE001 — the change stands
            log.error(
                "AUDIT %s NOT STORED workspace=%s user=%s (%s)",
                event,
                workspace_id,
                actor_id,
                type(error).__name__,
            )
