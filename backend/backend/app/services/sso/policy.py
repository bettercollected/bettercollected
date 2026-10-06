"""Single sign-on policy: SSO-required domains and the JIT default role.

A workspace that requires SSO (``sso_required``) refuses every other sign-in
(email code, Google) for addresses on its SSO domains, the verified domains
single sign-on applies to (``WorkspaceDomainService.sso_domains``). It only
takes effect while the instance has SSO switched on, the workspace is
available and it has an enabled connection: if any of those is missing the
members could not sign in with SSO either, so nothing is refused.

**Break-glass:** the workspace's owners (the billing owner and every member
with role OWNER) may still sign in with an email code, so a broken identity
provider cannot lock everyone out of the workspace. Google sign-in stays
refused for owners too: the code proves the owner's mailbox; a Google
account on the same address is a second path we don't need.

**Respondents:** the requirement covers the dashboard and the workspace's
own forms. On *another* workspace's forms such an address may still verify
itself with an email code, but only into a respondent-scoped session (no
workspace permissions, no creator or admin role).

**Refresh:** while the requirement holds, a session for an address on those
domains that did not sign in with SSO ends at its next refresh, member or
not, except the owners' email-code sessions and respondent-scoped ones.
See docs/sso.md.
"""

from http import HTTPStatus
from typing import List, Optional

from beanie import PydanticObjectId
from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.models.enum.workspace_roles import (
    WorkspaceRoles,
    canonical_role,
    has_owner_role,
    is_billing_owner,
)
from backend.app.repositories.sso_connection_repository import SsoConnectionRepository
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.services.domains.names import display_domain, domain_of
from backend.app.services.internal_auth import auth_service_headers
from backend.app.services.session_service import (
    OTP_METHOD,
    RESPONDENT_SCOPE,
    SSO_METHOD,
)
from backend.app.services.workspace_domain_service import WorkspaceDomainService
from backend.config import settings

SSO_REQUIRED = "sso_required"

# The role a first SSO sign-in gets unless the workspace chose another.
# The accepted design's default (docs/enterprise-access-model.md): Viewer.
DEFAULT_SSO_ROLE = WorkspaceRoles.VIEWER

# What an owner may pick as the SSO default, highest first. Owner, Admin and
# Privacy officer are granted by hand, never by an identity provider.
SSO_ASSIGNABLE_ROLES = (
    WorkspaceRoles.EDITOR,
    WorkspaceRoles.REVIEWER,
    WorkspaceRoles.VIEWER,
)


def assignable_sso_roles() -> List[str]:
    return [role.value for role in SSO_ASSIGNABLE_ROLES]


def default_sso_role(workspace: Optional[WorkspaceDocument]) -> WorkspaceRoles:
    """The workspace's configured default role (as the API speaks it), if it
    is (still) one SSO may give. A stored ``COLLABORATOR`` (the default
    before the new roles) is Editor and is kept, not migrated."""
    role = canonical_role(getattr(workspace, "sso_default_role", None))
    return role if role in SSO_ASSIGNABLE_ROLES else DEFAULT_SSO_ROLE


def sso_required_error(domain: str) -> HTTPException:
    return HTTPException(
        HTTPStatus.FORBIDDEN,
        {
            "code": SSO_REQUIRED,
            "message": (
                f"Your organisation requires single sign-on for {display_domain(domain)} "
                "addresses. Use “Sign in with SSO” instead."
            ),
        },
    )


class SsoPolicyService:
    def __init__(
        self,
        workspace_repo: WorkspaceRepository,
        domain_service: WorkspaceDomainService,
        connection_repo: SsoConnectionRepository,
        http_client=None,
        workspace_user_repo=None,
    ):
        self._workspace_repo = workspace_repo
        self._domains = domain_service
        self._connections = connection_repo
        self._http_client = http_client
        # the owners besides the billing owner (members with role OWNER)
        self._workspace_users = workspace_user_repo

    async def requiring_workspace(self, email: str) -> Optional[WorkspaceDocument]:
        """The workspace whose SSO requirement covers ``email``, if any."""
        if not settings.sso.ENABLED:
            return None
        claim = await self._domains.sso_domain_claim(email)
        if claim is None:
            return None
        workspace = await self._workspace_repo.find_by_id(claim.workspace_id)
        if workspace is None or workspace.disabled or not workspace.sso_required:
            return None
        if await self._connections.find_enabled(workspace.id) is None:
            return None
        return workspace

    async def check_code_sign_in(
        self, email: str, user_id: Optional[str] = None
    ) -> None:
        """Refuse a full email-code sign-in (the dashboard) for an
        SSO-required address, unless it is one of the workspace's owners'
        (break-glass). ``user_id``: the account, once known."""
        await self.code_sign_in_scope(email, user_id=user_id)

    async def code_sign_in_scope(
        self,
        email: str,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Optional[str]:
        """What an email-code sign-in for ``email`` may become: None for a
        full session, ``respondent`` for a session limited to answering the
        forms of ``workspace_id`` (another workspace than the one requiring
        SSO). Raises 403 ``sso_required`` otherwise. The workspace's owners
        keep full email-code sign-in (break-glass)."""
        workspace = await self.requiring_workspace(email)
        if workspace is None:
            return None
        if user_id is not None:
            is_owner = await self._is_owner(workspace, user_id)
        else:
            is_owner = await self._is_owner_email(workspace, email)
        if is_owner:
            logger.info(
                "SSO break-glass: an owner of workspace {} used an email code",
                workspace.id,
            )
            return None
        if workspace_id and str(workspace_id) != str(workspace.id):
            return RESPONDENT_SCOPE
        raise sso_required_error(domain_of(email) or "")

    async def session_must_end(self, email: str, session, user_id: str) -> bool:
        """Whether a session has to end at refresh because its address's
        domain requires single sign-on: any session that did not sign in
        with SSO, except the owners' email-code sessions (break-glass) and
        respondent-scoped sessions."""
        if session.method == SSO_METHOD or session.scope == RESPONDENT_SCOPE:
            return False
        workspace = await self.requiring_workspace(email or "")
        if workspace is None:
            return False
        if session.method == OTP_METHOD and await self._is_owner(workspace, user_id):
            return False
        logger.info(
            "SSO required in workspace {}: a {} session of user {} ended at refresh",
            workspace.id,
            session.method or "pre-SSO",
            user_id,
        )
        return True

    async def check_provider_sign_in(self, email: str) -> Optional[str]:
        """``sso_required`` when a Google (or other provider) sign-in for
        ``email`` must be refused, else None. No break-glass here."""
        if await self.requiring_workspace(email) is not None:
            return SSO_REQUIRED
        return None

    async def _owner_ids(self, workspace: WorkspaceDocument) -> List[str]:
        """The workspace's owners: the billing owner, and the members holding
        OWNER with an enabled membership."""
        owners = [str(workspace.owner_id)] if workspace.owner_id else []
        if self._workspace_users is None:
            return owners
        for membership in await self._workspace_users.get_workspace_users(
            workspace_id=workspace.id
        ):
            if (
                not membership.disabled
                and has_owner_role(membership.roles)
                and str(membership.user_id) not in owners
            ):
                owners.append(str(membership.user_id))
        return owners

    async def _is_owner(self, workspace: WorkspaceDocument, user_id) -> bool:
        if is_billing_owner(workspace, user_id):
            return True
        return str(user_id) in await self._owner_ids(workspace)

    async def _is_owner_email(self, workspace: WorkspaceDocument, email: str) -> bool:
        owner_ids = await self._owner_ids(workspace)
        if not owner_ids or self._http_client is None:
            return False
        try:
            reply = await self._http_client.get(
                settings.auth_settings.BASE_URL + "/users",
                params={"user_ids": owner_ids},
                headers=auth_service_headers(),
            )
        except Exception as error:  # noqa: BLE001 — fail closed (code refused)
            logger.warning("SSO break-glass check failed: {}", type(error).__name__)
            return False
        for user in (reply or {}).get("users_info") or []:
            owner_email = (user.get("email") or "").strip().lower()
            if owner_email and owner_email == (email or "").strip().lower():
                return True
        return False

    async def sso_users_of(
        self, workspace_id: PydanticObjectId, user_ids: List[str]
    ) -> List[str]:
        """Of ``user_ids``, those whose email is on one of the workspace's SSO
        domains (to offer revoking their sessions)."""
        domains = set(await self._domains.sso_domains(workspace_id))
        if not domains or not user_ids or self._http_client is None:
            return []
        reply = await self._http_client.get(
            settings.auth_settings.BASE_URL + "/users",
            params={"user_ids": [str(u) for u in user_ids]},
            headers=auth_service_headers(),
        )
        found = []
        for user in (reply or {}).get("users_info") or []:
            if domain_of(user.get("email") or "") in domains:
                found.append(str(user.get("_id") or user.get("id")))
        return found
