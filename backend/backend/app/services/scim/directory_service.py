"""Workspace directory sync administration (docs/sso.md, "Directory sync").

Like the SSO configuration, every change is **Owner only**
(``AuthorizationService.require_owner``): a directory decides who joins the
workspace and with which role, ADMIN included. Owner and Admins
(``security.manage``) see the status. A directory needs single sign-on on the
instance, ``SCIM_WEBHOOK_URL`` and a verified domain of the workspace.

The SCIM bearer token is returned once, by create and rotate, and never
stored here; the webhook secret is stored encrypted and never returned.
"""

import datetime as dt
import secrets
from http import HTTPStatus
from typing import Dict, List, Optional

from beanie import PydanticObjectId
from common.models.user import User
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.repositories.scim_repository import (
    ScimDirectoryExists,
    ScimDirectoryRepository,
    ScimGroupMemberRepository,
    ScimGroupRepository,
    ScimUserRepository,
)
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.schemas.scim import (
    DIRECTORY_TYPES,
    ScimDirectoryDocument,
    ScimUserState,
)
from backend.app.services.authorization_service import AuthorizationService
from backend.app.services.scim.polis_dsync import (
    PolisDirectoryClient,
    scim_endpoint,
    scim_secret,
)
from backend.app.services.scim.roles import is_mappable, mappable_roles
from backend.app.services.scim.sync_service import (
    REASON_MESSAGES,
    ScimSyncService,
    SyncCounts,
)
from backend.app.services.sso.polis_client import PolisError, PolisUnavailable
from backend.app.services.sso.policy import default_sso_role
from backend.app.services.workspace_domain_service import WorkspaceDomainService
from backend.config import settings

MAX_FAILURES_SHOWN = 50


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class CreateDirectoryDto(_CamelModel):
    type: str = Field("generic-scim-v2", max_length=64)
    name: Optional[str] = Field(None, max_length=100)


class GroupRoleDto(_CamelModel):
    # a workspace role, or None to map the group to nothing
    role: Optional[str] = Field(None, max_length=64)


class DirectoryDto(_CamelModel):
    id: str
    type: str
    type_label: str
    name: str
    scim_endpoint: str
    created_at: Optional[dt.datetime] = None
    created_by: Optional[str] = None
    rotated_at: Optional[dt.datetime] = None
    last_event_at: Optional[dt.datetime] = None
    last_event_type: Optional[str] = None
    last_resync_at: Optional[dt.datetime] = None
    last_resync_summary: Optional[Dict[str, int]] = None
    last_resync_error: Optional[str] = None

    @classmethod
    def of(cls, d: ScimDirectoryDocument) -> "DirectoryDto":
        return cls(
            id=str(d.id),
            type=d.type,
            type_label=DIRECTORY_TYPES.get(d.type, d.type),
            name=d.name,
            scim_endpoint=d.scim_endpoint,
            created_at=d.created_at,
            created_by=d.created_by,
            rotated_at=d.rotated_at,
            last_event_at=d.last_event_at,
            last_event_type=d.last_event_type,
            last_resync_at=d.last_resync_at,
            last_resync_summary=d.last_resync_summary,
            last_resync_error=d.last_resync_error,
        )


class DirectoryCredentialsDto(_CamelModel):
    """Shown once: what the identity provider is configured with."""

    directory: DirectoryDto
    scim_endpoint: str
    bearer_token: str


class GroupDto(_CamelModel):
    id: str
    name: str
    role: Optional[str] = None
    members: int = 0


class DirectoryIssueDto(_CamelModel):
    email: str
    state: str
    reason: str
    message: str
    at: Optional[dt.datetime] = None


class DirectoryTypeDto(_CamelModel):
    type: str
    label: str


class DirectoryOverviewDto(_CamelModel):
    # SSO and SCIM are configured on this instance
    available: bool
    # the workspace has a verified domain (a directory needs one)
    has_verified_domain: bool = False
    directory: Optional[DirectoryDto] = None
    types: List[DirectoryTypeDto] = []
    counts: Dict[str, int] = {}
    issues: List[DirectoryIssueDto] = []
    groups: List[GroupDto] = []
    default_role: str
    mappable_roles: List[str]
    can_manage: bool = False


class ResyncDto(_CamelModel):
    directory: DirectoryDto
    summary: Dict[str, int]


def _refused(status: HTTPStatus, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, content={"code": code, "message": message})


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _polis_error(error: PolisError) -> HTTPException:
    if isinstance(error, PolisUnavailable) or error.status >= 500:
        return _refused(
            HTTPStatus.SERVICE_UNAVAILABLE,
            "scim_unavailable",
            "The directory sync service is not reachable.",
        )
    return _refused(
        HTTPStatus.UNPROCESSABLE_ENTITY,
        "scim_refused",
        "The directory sync service refused the request.",
    )


def scim_available() -> bool:
    return bool(settings.sso.is_configured and settings.scim.webhook_base)


class ScimDirectoryService:
    def __init__(
        self,
        authorization_service: AuthorizationService,
        directory_repo: ScimDirectoryRepository,
        user_repo: ScimUserRepository,
        group_repo: ScimGroupRepository,
        member_repo: ScimGroupMemberRepository,
        workspace_repo: WorkspaceRepository,
        domain_service: WorkspaceDomainService,
        sync_service: ScimSyncService,
        polis: PolisDirectoryClient,
        crypto,
    ):
        self._authorization = authorization_service
        self._directories = directory_repo
        self._users = user_repo
        self._groups = group_repo
        self._members = member_repo
        self._workspace_repo = workspace_repo
        self._domains = domain_service
        self._sync = sync_service
        self._polis = polis
        self._crypto = crypto

    # -- access ---------------------------------------------------------------
    async def _authorize(self, workspace_id, user: User) -> None:
        await self._authorization.authorize(
            user, Permission.SECURITY_MANAGE, workspace_id
        )

    async def _authorize_owner(self, workspace_id, user: User) -> None:
        await self._authorize(workspace_id, user)
        await self._authorization.require_owner(user, workspace_id)

    @staticmethod
    def _require_available() -> None:
        if not scim_available():
            raise _refused(
                HTTPStatus.NOT_FOUND,
                "scim_disabled",
                "Directory sync is not enabled on this instance.",
            )

    async def _directory(self, workspace_id) -> ScimDirectoryDocument:
        directory = await self._directories.find_by_workspace(
            PydanticObjectId(workspace_id)
        )
        if directory is None:
            raise _refused(
                HTTPStatus.NOT_FOUND,
                "scim_no_directory",
                "This workspace has no directory.",
            )
        return directory

    # -- read -----------------------------------------------------------------
    async def overview(self, workspace_id, user: User) -> DirectoryOverviewDto:
        await self._authorize(workspace_id, user)
        workspace = await self._workspace_repo.find_by_id(workspace_id)
        directory = await self._directories.find_by_workspace(
            PydanticObjectId(workspace_id)
        )
        dto = DirectoryOverviewDto(
            available=scim_available(),
            has_verified_domain=bool(await self._domains.sso_domains(workspace_id)),
            directory=DirectoryDto.of(directory) if directory else None,
            types=[
                DirectoryTypeDto(type=t, label=l) for t, l in DIRECTORY_TYPES.items()
            ],
            default_role=default_sso_role(workspace).value,
            mappable_roles=mappable_roles(),
            can_manage=await self._authorization.is_owner(user, workspace_id),
        )
        if directory is None:
            return dto
        users = await self._users.list_by_directory(directory.id)
        counts = {state.value: 0 for state in ScimUserState}
        for record in users:
            counts[record.state.value] = counts.get(record.state.value, 0) + 1
        counts["users"] = len(users)
        dto.counts = counts
        issues = [
            r
            for r in users
            if r.state in (ScimUserState.FAILED, ScimUserState.IGNORED) and r.reason
        ]
        issues.sort(key=lambda r: r.updated_at or r.created_at, reverse=True)
        dto.issues = [
            DirectoryIssueDto(
                email=r.email,
                state=r.state.value,
                reason=r.reason,
                message=REASON_MESSAGES.get(r.reason, r.reason),
                at=r.updated_at,
            )
            for r in issues[:MAX_FAILURES_SHOWN]
        ]
        links = await self._members.list_by_directory(directory.id)
        per_group: Dict[str, int] = {}
        for link in links:
            per_group[str(link.group_id)] = per_group.get(str(link.group_id), 0) + 1
        dto.groups = [
            GroupDto(
                id=str(g.id),
                name=g.name,
                role=g.role,
                members=per_group.get(str(g.id), 0),
            )
            for g in sorted(
                await self._groups.list_by_directory(directory.id),
                key=lambda g: g.name.lower(),
            )
        ]
        return dto

    # -- create, rotate, delete -----------------------------------------------
    def _webhook_url(self, directory_id: PydanticObjectId) -> str:
        return f"{settings.scim.webhook_base}/{directory_id}"

    async def create(
        self, workspace_id, request: CreateDirectoryDto, user: User
    ) -> DirectoryCredentialsDto:
        await self._authorize_owner(workspace_id, user)
        self._require_available()
        if request.type not in DIRECTORY_TYPES:
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "invalid_directory_type",
                "Choose one of the listed directory types.",
            )
        if not await self._domains.sso_domains(workspace_id):
            raise _refused(
                HTTPStatus.CONFLICT,
                "sso_domain_required",
                "Verify an email domain first: the directory only provisions "
                "addresses on verified domains.",
            )
        if await self._directories.find_by_workspace(PydanticObjectId(workspace_id)):
            raise _refused(
                HTTPStatus.CONFLICT,
                "scim_directory_exists",
                "This workspace already has a directory.",
            )
        directory_id = PydanticObjectId()
        name = (request.name or "").strip() or DIRECTORY_TYPES[request.type]
        webhook_secret = secrets.token_urlsafe(32)
        try:
            created = await self._polis.create_directory(
                str(workspace_id),
                name,
                request.type,
                self._webhook_url(directory_id),
                webhook_secret,
            )
        except PolisError as error:
            raise _polis_error(error)
        document = ScimDirectoryDocument(
            id=directory_id,
            workspace_id=PydanticObjectId(workspace_id),
            polis_directory_id=str(created["id"]),
            polis_tenant=str(workspace_id),
            polis_product=settings.sso.POLIS_PRODUCT,
            type=request.type,
            name=name,
            scim_endpoint=scim_endpoint(created),
            webhook_secret=self._crypto.encrypt(webhook_secret),
            created_by=str(user.id),
        )
        try:
            await self._directories.create(document)
        except ScimDirectoryExists:
            # a parallel create won: remove the directory we just made
            await self._delete_in_polis(document.polis_directory_id)
            raise _refused(
                HTTPStatus.CONFLICT,
                "scim_directory_exists",
                "This workspace already has a directory.",
            )
        logger.info(
            "SCIM directory {} ({}) created in workspace {} by {}",
            document.id,
            document.type,
            workspace_id,
            user.id,
        )
        return DirectoryCredentialsDto(
            directory=DirectoryDto.of(document),
            scim_endpoint=document.scim_endpoint,
            bearer_token=scim_secret(created),
        )

    async def rotate(self, workspace_id, user: User) -> DirectoryCredentialsDto:
        """A new SCIM token. Polis can't change a directory's token, so the
        directory is replaced in Polis: a new base URL and token (shown once),
        a new webhook secret, and the old directory deleted (its token stops
        working at once). Members, groups and their mappings are kept and
        matched to what the identity provider sends next (users by email,
        groups by name)."""
        await self._authorize_owner(workspace_id, user)
        self._require_available()
        directory = await self._directory(workspace_id)
        webhook_secret = secrets.token_urlsafe(32)
        try:
            created = await self._polis.create_directory(
                str(workspace_id),
                directory.name,
                directory.type,
                self._webhook_url(directory.id),
                webhook_secret,
            )
        except PolisError as error:
            raise _polis_error(error)
        old_polis_id = directory.polis_directory_id
        now = _now()
        directory.polis_directory_id = str(created["id"])
        directory.scim_endpoint = scim_endpoint(created)
        directory.webhook_secret = self._crypto.encrypt(webhook_secret)
        directory.rotated_at = now
        directory.rotated_by = str(user.id)
        directory.updated_at = now
        await self._directories.save(directory)
        for record in await self._users.list_by_directory(directory.id):
            if not record.deleted and not record.replaced:
                record.replaced = True
                await self._users.save(record)
        for group in await self._groups.list_by_directory(directory.id):
            if not group.replaced:
                group.replaced = True
                await self._groups.save(group)
        await self._delete_in_polis(old_polis_id)
        logger.info(
            "SCIM directory {} of workspace {} rotated by {}",
            directory.id,
            workspace_id,
            user.id,
        )
        return DirectoryCredentialsDto(
            directory=DirectoryDto.of(directory),
            scim_endpoint=directory.scim_endpoint,
            bearer_token=scim_secret(created),
        )

    async def _delete_in_polis(self, polis_directory_id: str) -> None:
        try:
            await self._polis.delete_directory(polis_directory_id)
        except PolisError:
            logger.warning(
                "Could not delete Polis directory {}; delete it by hand",
                polis_directory_id,
            )

    async def delete(self, workspace_id, user: User) -> None:
        """Stop syncing. Members stay as they are (an admin decides), and so
        do their accounts and forms."""
        await self._authorize_owner(workspace_id, user)
        directory = await self._directory(workspace_id)
        if settings.sso.is_configured:
            try:
                await self._polis.delete_directory(directory.polis_directory_id)
            except PolisError as error:
                raise _polis_error(error)
        await self._forget(directory)
        logger.info(
            "SCIM directory {} of workspace {} deleted by {}",
            directory.id,
            workspace_id,
            user.id,
        )

    async def _forget(self, directory: ScimDirectoryDocument) -> None:
        await self._members.delete_by_directory(directory.id)
        await self._groups.delete_by_directory(directory.id)
        await self._users.delete_by_directory(directory.id)
        await self._directories.delete(directory.id)

    # -- mapping --------------------------------------------------------------
    async def set_group_role(
        self, workspace_id, group_id: str, request: GroupRoleDto, user: User
    ) -> GroupDto:
        await self._authorize_owner(workspace_id, user)
        directory = await self._directory(workspace_id)
        group = await self._groups.get(group_id)
        if group is None or group.directory_id != directory.id:
            raise _refused(HTTPStatus.NOT_FOUND, "not_found", "No such group.")
        role = request.role or None
        if role is not None and not is_mappable(role):
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "invalid_role",
                "That role can't be given by a directory group.",
            )
        group.role = role
        group.role_changed_by = str(user.id)
        group.updated_at = _now()
        await self._groups.save(group)
        changed = await self._sync.recompute_group(group)
        logger.info(
            "SCIM group {} of workspace {} maps to {} ({} roles changed) by {}",
            group.id,
            workspace_id,
            role,
            changed,
            user.id,
        )
        members = len(await self._members.list_by_group(group.id))
        return GroupDto(id=str(group.id), name=group.name, role=role, members=members)

    # -- resync ---------------------------------------------------------------
    async def resync(self, workspace_id, user: User) -> ResyncDto:
        await self._authorize_owner(workspace_id, user)
        self._require_available()
        directory = await self._directory(workspace_id)
        summary = await self.resync_directory(directory, str(user.id))
        directory = await self._directory(workspace_id)
        if directory.last_resync_error:
            raise _refused(
                HTTPStatus.SERVICE_UNAVAILABLE,
                directory.last_resync_error,
                "The directory sync service is not reachable.",
            )
        return ResyncDto(directory=DirectoryDto.of(directory), summary=summary)

    async def resync_directory(
        self, directory: ScimDirectoryDocument, by: str
    ) -> Dict[str, int]:
        """Pull the directory's users and groups from Polis and apply them
        (the admin button, the CLI and the nightly job)."""
        page = settings.scim.RECONCILE_PAGE_SIZE
        tenant, polis_id = directory.polis_tenant, directory.polis_directory_id
        counts = SyncCounts()
        error = None
        try:
            users = await self._polis.list_users(tenant, polis_id, page)
            groups = []
            for group in await self._polis.list_groups(tenant, polis_id, page):
                group_id = str(group.get("id") or "")
                if not group_id:
                    continue
                members = await self._polis.list_group_members(
                    tenant, polis_id, group_id, page
                )
                groups.append((group, members))
            counts = await self._sync.reconcile(directory, users, groups)
        except PolisError:
            error = "scim_unavailable"
        now = _now()
        fresh = await self._directories.get(directory.id) or directory
        fresh.last_resync_at = now
        fresh.last_resync_by = by
        fresh.last_resync_error = error
        if error is None:
            fresh.last_resync_summary = counts.summary()
        fresh.updated_at = now
        await self._directories.save(fresh)
        logger.info(
            "SCIM directory {} resynced by {}: {}",
            directory.id,
            by,
            error or counts.summary(),
        )
        return counts.summary()

    async def resync_all(self, by: str = "schedule") -> Dict[str, int]:
        """Every directory (the nightly job and ``--all``)."""
        done = failed = 0
        if not scim_available():
            return {"directories": 0, "failed": 0}
        for directory in await self._directories.list_all():
            await self.resync_directory(directory, by)
            fresh = await self._directories.get(directory.id)
            if fresh is not None and fresh.last_resync_error:
                failed += 1
            else:
                done += 1
        return {"directories": done, "failed": failed}

    # -- workspace deletion ---------------------------------------------------
    async def release_workspaces(self, workspace_ids: List[PydanticObjectId]) -> int:
        removed = 0
        for workspace_id in workspace_ids or []:
            directory = await self._directories.find_by_workspace(
                PydanticObjectId(workspace_id)
            )
            if directory is None:
                continue
            if settings.sso.is_configured:
                await self._delete_in_polis(directory.polis_directory_id)
            await self._forget(directory)
            removed += 1
        return removed
