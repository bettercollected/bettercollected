"""The workspace selection screen after sign-in.

After a plain sign-in the user picks the workspace to open. The list is
built here, on the server, from the user's own memberships only: an enabled
membership of an available workspace, or an owner's membership of a disabled
one (a downgraded workspace stays reachable read-only for its owners and for
no one else, see ``authorization_service``). Nothing about any other
workspace is returned, not even whether it exists.

A sign-in that started from a link to a workspace's dashboard page (``next``)
goes straight back there when the user may open that workspace. Otherwise the
answer carries the notice ``no_access``, the same for a workspace the user is
not a member of and for one that does not exist.
"""

from typing import List, Optional
from urllib.parse import unquote, urlsplit

from common.enums.roles import Roles
from common.models.user import User
from fastapi_camelcase import CamelModel

from backend.app.models.enum.workspace_roles import is_owner_membership, primary_role
from backend.app.repositories.postgres.identity import (
    PostgresWorkspaceRepository,
    PostgresWorkspaceUserRepository,
)
from backend.app.services.session_service import RESPONDENT_SCOPE
from backend.config import settings

NO_ACCESS = "no_access"

# a sign-in target longer than this is not a link anyone followed
MAX_NEXT_LENGTH = 2048


class WorkspaceChoiceDto(CamelModel):
    id: str
    title: Optional[str] = None
    workspace_name: str
    profile_image: Optional[str] = None
    # the user's role there: OWNER for every owner, else the membership's
    role: Optional[str] = None
    is_owner: bool = False
    # the workspace's own domain, only while it is verified and in use
    custom_domain: Optional[str] = None
    # read-only for its owners (the billing owner's plan was downgraded)
    disabled: bool = False
    # the workspace requires its single sign-on and this session did not
    # come from it: selecting it starts that sign-in instead
    sso_required: bool = False


class WorkspaceSelectionDto(CamelModel):
    workspaces: List[WorkspaceChoiceDto]
    # whether the user may create a workspace now (creator, plan, limit)
    can_create_workspace: bool = False
    is_creator: bool = False
    # where to go right away: the dashboard page the sign-in started from,
    # in a workspace the user may open
    next: Optional[str] = None
    # ``no_access``: the sign-in started from a workspace page the user
    # can't open (or that doesn't exist; the two are not told apart)
    notice: Optional[str] = None


class WorkspaceTargetDto(CamelModel):
    """Where a sign-in (or a visit) that names ``next`` goes: ``next`` when
    the user may open that workspace page, else ``notice`` (``no_access``
    for a workspace they can't open or that doesn't exist), or neither (no
    workspace named, or one that needs its single sign-on first)."""

    next: Optional[str] = None
    notice: Optional[str] = None


def app_path(value: Optional[str]) -> Optional[str]:
    """``value`` as a path of this app (path and query, the fragment
    dropped), or None for anything else: an absolute or scheme-relative URL,
    a backslash (browsers read ``/\\host`` as another host), control
    characters, dot segments, or an overlong value."""
    if not isinstance(value, str) or not value or len(value) > MAX_NEXT_LENGTH:
        return None
    if not value.startswith("/") or value.startswith("//") or "\\" in value:
        return None
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in value):
        return None
    parts = urlsplit(value)
    if parts.scheme or parts.netloc:
        return None
    if any(unquote(segment) in (".", "..") for segment in parts.path.split("/")):
        return None
    return parts.path + (f"?{parts.query}" if parts.query else "")


def target_workspace_name(path: str) -> Optional[str]:
    """The workspace handle a dashboard page (``/<handle>/dashboard...``)
    names, else None: a path that names no workspace."""
    segments = urlsplit(path).path.split("/")
    if len(segments) >= 3 and segments[1] and segments[2] == "dashboard":
        return unquote(segments[1])
    return None


def _sort_key(choice: WorkspaceChoiceDto):
    return ((choice.title or choice.workspace_name).casefold(), choice.workspace_name)


class WorkspaceSelectionService:
    def __init__(
        self,
        workspace_repo: PostgresWorkspaceRepository,
        workspace_user_repo: PostgresWorkspaceUserRepository,
        sso_policy=None,
    ):
        self._workspace_repo = workspace_repo
        self._workspace_user_repo = workspace_user_repo
        self._sso_policy = sso_policy

    async def choices(self, user: User) -> List[WorkspaceChoiceDto]:
        """The workspaces ``user`` may pick, ordered by name. A
        respondent-scoped session (docs/sso.md) holds no workspace
        permission anywhere, so it has none."""
        if user.session_scope == RESPONDENT_SCOPE:
            return []
        memberships = {
            str(membership.workspace_id): membership
            for membership in await self._workspace_user_repo.get_mine_workspaces(
                user_id=user.id
            )
            if not membership.disabled
        }
        if not memberships:
            return []
        workspaces = await self._workspace_repo.get_workspace_by_ids(
            workspace_ids=[m.workspace_id for m in memberships.values()]
        )
        sso_workspace_id = await self._unmet_sso_workspace_id(user)
        choices = []
        for workspace in workspaces:
            membership = memberships.get(str(workspace.id))
            is_owner = is_owner_membership(workspace, membership)
            if workspace.disabled and not is_owner:
                # a downgraded workspace is its owners' alone
                continue
            choices.append(
                WorkspaceChoiceDto(
                    id=str(workspace.id),
                    title=workspace.title,
                    workspace_name=workspace.workspace_name,
                    profile_image=workspace.profile_image,
                    role=primary_role(membership.roles, is_owner=is_owner),
                    is_owner=is_owner,
                    custom_domain=(
                        workspace.custom_domain
                        if workspace.custom_domain
                        and workspace.custom_domain_verified
                        and not workspace.custom_domain_disabled
                        else None
                    ),
                    disabled=bool(workspace.disabled),
                    sso_required=str(workspace.id) == sso_workspace_id,
                )
            )
        return sorted(choices, key=_sort_key)

    async def selection(
        self, user: User, next_path: Optional[str] = None
    ) -> WorkspaceSelectionDto:
        workspaces = await self.choices(user)
        is_creator = user.session_scope != RESPONDENT_SCOPE and Roles.FORM_CREATOR in (
            user.roles or []
        )
        target = self._resolve(workspaces, next_path)
        return WorkspaceSelectionDto(
            workspaces=workspaces,
            is_creator=is_creator,
            can_create_workspace=is_creator and await self._may_create(user),
            next=target.next,
            notice=target.notice,
        )

    async def target(
        self, user: User, next_path: Optional[str] = None
    ) -> WorkspaceTargetDto:
        """Only where ``next`` goes, for the dashboard's own check on every
        workspace page: the same answer as ``selection`` without the parts
        the check doesn't need (whether the user may create a workspace)."""
        return self._resolve(await self.choices(user), next_path)

    @staticmethod
    def _resolve(
        workspaces: List[WorkspaceChoiceDto], next_path: Optional[str]
    ) -> WorkspaceTargetDto:
        path = app_path(next_path)
        handle = target_workspace_name(path) if path else None
        if handle is None:
            # no target, an unusable one, or one that names no workspace:
            # the plain sign-in
            return WorkspaceTargetDto()
        target = next((w for w in workspaces if w.workspace_name == handle), None)
        if target is None:
            return WorkspaceTargetDto(notice=NO_ACCESS)
        if target.sso_required:
            # the screen, whose row starts that workspace's sign-in
            return WorkspaceTargetDto()
        return WorkspaceTargetDto(next=path)

    async def _may_create(self, user: User) -> bool:
        """The rule ``create_non_default_workspace`` applies: Pro, and fewer
        workspaces billed to the user than the limit."""
        if getattr(user.plan, "value", user.plan) != "PRO":
            return False
        owned = await self._workspace_repo.get_user_workspaces(user.id)
        return len(owned) < settings.api_settings.ALLOWED_WORKSPACES

    async def _unmet_sso_workspace_id(self, user: User) -> Optional[str]:
        if self._sso_policy is None:
            return None
        workspace = await self._sso_policy.unmet_requirement(
            user.sub, user.auth_method, user.session_scope, user.id
        )
        return str(workspace.id) if workspace is not None else None
