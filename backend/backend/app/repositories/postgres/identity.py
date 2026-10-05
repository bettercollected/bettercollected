"""Postgres twins of the identity-group repositories.

Each class mirrors the public surface of its Mongo original method for method,
including its quirks (404 vs None, the document layer's NotFoundError), so the
RoutingRepository can serve either store. Queries use the spine columns of the
rows in :mod:`backend.db.models`; documents cross the boundary unchanged.

One method crosses a group boundary: ``get_workspace_with_action_by_id`` is a
``$lookup`` from workspaces (identity) into workspace_actions (actions) in
Mongo. Groups cut over independently, so the twin composes the two reads
through the *routed* actions repository instead of a SQL join — whichever
store currently serves actions is the one consulted. Joins stay SQL only
within a group; R3 can collapse this one once both groups live in Postgres.
"""

import datetime
import secrets
from datetime import timedelta, timezone
from http import HTTPStatus
from typing import Any, Dict, List, Optional

from beanie import PydanticObjectId
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import and_, func, not_, or_, select
from sqlalchemy.exc import IntegrityError

from backend.app.exceptions import HTTPException
from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.models.invitation_request import InvitationRequest
from backend.app.repositories.metric_periods import (
    object_id_at,
    postgres_counts_per_period,
)
from backend.app.repositories.sso_connection_repository import SsoConnectionExists
from backend.app.repositories.sso_used_state_repository import StateAlreadyUsed
from backend.app.repositories.scim_repository import (
    ScimDirectoryExists,
    ScimEventSeen,
)
from backend.app.schemas.scim import (
    ScimDirectoryDocument,
    ScimEventDocument,
    ScimGroupDocument,
    ScimGroupMemberDocument,
    ScimUserDocument,
)
from backend.app.schemas.sso_used_state import SsoUsedStateDocument
from backend.app.schemas.session import SessionDocument
from backend.app.schemas.sso_connection import (
    SsoConnectionDocument,
    SsoConnectionStatus,
)
from backend.app.schemas.user_tags import UserTagsDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.repositories.workspace_domain_repository import (
    DomainAlreadyClaimed,
    DomainVerifiedElsewhere,
)
from backend.app.schemas.workspace_api_key import WorkspaceAPIKeyDocument
from backend.app.schemas.workspace_domain import DomainStatus, WorkspaceDomainDocument
from backend.app.schemas.workspace_invitation import WorkspaceUserInvitesDocument
from backend.app.schemas.workspace_user import (
    DISABLED_BY_PLAN,
    WorkspaceUserDocument,
)
from backend.app.services.auth_cookie_service import get_expiry_epoch_after
from backend.db.base import SCHEMA
from backend.db.models import (
    ScimDirectoryRow,
    ScimEventRow,
    ScimGroupMemberRow,
    ScimGroupRow,
    ScimUserRow,
    SessionRow,
    SsoConnectionRow,
    SsoUsedStateRow,
    UserTagsRow,
    WorkspaceApiKeyRow,
    WorkspaceDomainRow,
    WorkspaceInviteRow,
    WorkspaceRow,
    WorkspaceUserRow,
)
from common.constants import MESSAGE_NOT_FOUND
from common.db import (
    PostgresRepositoryBase,
    from_canonical_document,
    from_row_doc,
    row_values,
    to_bson_dict,
)
from common.enums.workspace_invitation_status import InvitationStatus
from common.models.user import User


def _oid(value: Any) -> str:
    """Spine ids are ObjectId hex strings; accept whatever the callers pass."""
    return str(value)


class PostgresWorkspaceRepository(PostgresRepositoryBase):
    row = WorkspaceRow
    document = WorkspaceDocument

    def __init__(self, session_factory, action_repository):
        super().__init__(session_factory)
        self._actions = action_repository

    # BaseRepository stubs, unused — kept so both stores expose the same surface.
    async def list(self):
        pass

    async def get(self, item_id, provider):
        pass

    async def add(self, item):
        pass

    async def delete(self, item_id, provider):
        pass

    async def update(
        self, item_id: PydanticObjectId, item: WorkspaceDocument
    ) -> WorkspaceDocument:
        if await self.one(WorkspaceRow.id == _oid(item_id)) is None:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Workspace not found")
        return await self.upsert(item)

    async def get_workspace_by_id(
        self, workspace_id: PydanticObjectId
    ) -> WorkspaceDocument:
        workspace = await self.one(WorkspaceRow.id == _oid(workspace_id))
        if not workspace:
            raise HTTPException(HTTPStatus.NOT_FOUND)
        return workspace

    async def find_by_id(
        self, workspace_id: PydanticObjectId
    ) -> Optional[WorkspaceDocument]:
        return await self.one(WorkspaceRow.id == _oid(workspace_id))

    async def find_by_name(self, workspace_name: str) -> Optional[WorkspaceDocument]:
        return await self.one(WorkspaceRow.workspace_name == workspace_name)

    async def find_by_custom_domain(
        self, custom_domain: str
    ) -> Optional[WorkspaceDocument]:
        return await self.one(WorkspaceRow.custom_domain == custom_domain)

    async def find_by_custom_domain_id(
        self, domain_id: str
    ) -> Optional[WorkspaceDocument]:
        return await self.one(WorkspaceRow.doc["custom_domain_id"].astext == domain_id)

    async def get_or_404(self, workspace_id: PydanticObjectId) -> WorkspaceDocument:
        return await self.get_or_raise(workspace_id)

    async def save(self, workspace: WorkspaceDocument) -> WorkspaceDocument:
        return await self.upsert(workspace)

    async def set_fields(
        self, workspace: WorkspaceDocument, fields: Dict[str, Any]
    ) -> None:
        # Beanie's document.update({"$set": ...}) also refreshes the instance.
        for path, value in fields.items():
            *parents, leaf = path.split(".")
            target: Any = workspace
            for part in parents:
                target = (
                    target[part] if isinstance(target, dict) else getattr(target, part)
                )
            if isinstance(target, dict):
                target[leaf] = value
            else:
                setattr(target, leaf, value)
        await self.upsert(workspace)

    async def set_owner_if(
        self, workspace_id: PydanticObjectId, expected_owner_id: str, new_owner_id: str
    ) -> Optional[WorkspaceDocument]:
        """Twin of the Mongo conditional ``$set``: the row is locked while the
        owner is compared and replaced."""
        async with self._session() as session, session.begin():
            doc = (
                await session.execute(
                    select(WorkspaceRow.doc)
                    .where(WorkspaceRow.id == _oid(workspace_id))
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                return None
            stored = from_row_doc(WorkspaceDocument, doc)
            if str(stored.owner_id) != str(expected_owner_id):
                return None
            stored.owner_id = str(new_owner_id)
            await session.execute(self._upsert_statement(row_values(stored)))
        return stored

    async def get_workspace_by_query(self, query: str):
        disabled = WorkspaceRow.doc["custom_domain_disabled"]
        workspace = await self.one(
            or_(
                WorkspaceRow.workspace_name == query,
                and_(
                    WorkspaceRow.custom_domain == query,
                    or_(
                        not_(WorkspaceRow.doc.has_key("custom_domain_disabled")),
                        getattr(func, SCHEMA).bc_bool(disabled).is_(False),
                    ),
                ),
            )
        )
        if not workspace:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                content="The page you are looking is unavailable.",
            )
        return workspace

    async def get_user_workspaces(self, owner_id: str):
        return await self.many(WorkspaceRow.owner_id == owner_id)

    async def get_workspace_by_ids(self, workspace_ids: List[PydanticObjectId]):
        return await self.many(WorkspaceRow.id.in_([_oid(i) for i in workspace_ids]))

    async def get_default_workspace_by_owner_id(
        self, owner_id: str
    ) -> WorkspaceDocument:
        return await self.one(
            WorkspaceRow.owner_id == owner_id, WorkspaceRow.is_default.is_(True)
        )

    async def count_workspaces(
        self, created_since: Optional[datetime.datetime] = None
    ) -> int:
        if created_since is None:
            return await self.count()
        return await self.count(WorkspaceRow.id >= str(object_id_at(created_since)))

    async def count_disabled_workspaces(self) -> int:
        return await self.count(WorkspaceRow.disabled.is_(True))

    async def count_workspaces_created_per_period(
        self, boundaries: List[datetime.datetime]
    ) -> List[int]:
        return await postgres_counts_per_period(
            self, WorkspaceRow.id, [str(object_id_at(b)) for b in boundaries]
        )

    async def delete_workspaces_with_ids(self, workspace_ids: List[PydanticObjectId]):
        return await self.delete_where(
            WorkspaceRow.id.in_([_oid(i) for i in workspace_ids])
        )

    async def get_workspace_with_action_by_id(
        self, workspace_id: PydanticObjectId, action_id: PydanticObjectId
    ):
        """The raw-document shape of the Mongo aggregation: the workspace with
        ``parameters.<action_id>`` / ``secrets.<action_id>`` from its
        workspace_actions entry and ``id`` set. See the module docstring for
        why the second read goes through the routed actions repository."""
        async with self._session() as session:
            raw = (
                await session.execute(
                    select(WorkspaceRow.doc).where(
                        WorkspaceRow.id == _oid(workspace_id)
                    )
                )
            ).scalar_one_or_none()
        workspace_action = (
            None
            if raw is None
            else await self._actions.get_workspace_action(
                workspace_id=PydanticObjectId(_oid(workspace_id)),
                action_id=PydanticObjectId(_oid(action_id)),
            )
        )
        if raw is None or workspace_action is None:
            raise HTTPException(status_code=404, content="Workspace not found")
        workspace = from_canonical_document(raw)
        action = to_bson_dict(workspace_action)
        for key in ("parameters", "secrets"):
            if key in action:  # $set of a missing path adds nothing
                workspace.setdefault(key, {})[str(action_id)] = action[key]
        workspace["id"] = PydanticObjectId(_oid(workspace_id))
        return workspace


class PostgresWorkspaceUserRepository(PostgresRepositoryBase):
    row = WorkspaceUserRow
    document = WorkspaceUserDocument

    async def has_user_access_in_workspace(
        self, workspace_id: PydanticObjectId, user: User
    ) -> bool:
        if not user or not workspace_id:
            return False
        workspace_user = await self.find_workspace_user(workspace_id, user.id)
        return True if workspace_user and not workspace_user.disabled else False

    async def is_user_admin_in_workspace(
        self, workspace_id: PydanticObjectId, user: User
    ) -> bool:
        if not user or not workspace_id:
            return False
        workspace_user = await self.find_workspace_user(workspace_id, user.id)
        # The original calls WorkspaceDocument.get unconditionally: a missing
        # workspace raises NotFoundError even when the user is not a member.
        workspace = WorkspaceDocument.verify_doc_exists(
            await self.one_of(
                WorkspaceRow, WorkspaceDocument, WorkspaceRow.id == _oid(workspace_id)
            ),
            {"id": workspace_id},
        )
        return (
            True
            if workspace_user
            and not workspace_user.disabled
            and (
                WorkspaceRoles.ADMIN in workspace_user.roles
                or workspace.owner_id == user.id
            )
            else False
        )

    async def get_workspace_users(self, workspace_id: PydanticObjectId):
        return await self.many(WorkspaceUserRow.workspace_id == _oid(workspace_id))

    async def find_workspace_user(
        self, workspace_id: PydanticObjectId, user_id: PydanticObjectId
    ) -> Optional[WorkspaceUserDocument]:
        return await self.one(
            WorkspaceUserRow.workspace_id == _oid(workspace_id),
            WorkspaceUserRow.user_id == _oid(user_id),
        )

    async def save(self, workspace_user: WorkspaceUserDocument):
        return await self.upsert(workspace_user)

    async def add_if_absent(
        self, workspace_user: WorkspaceUserDocument
    ) -> WorkspaceUserDocument:
        existing = await self.find_workspace_user(
            workspace_user.workspace_id, workspace_user.user_id
        )
        if existing is not None and str(existing.id) != str(workspace_user.id):
            return existing
        try:
            return await self.upsert(workspace_user)
        except IntegrityError:
            existing = await self.find_workspace_user(
                workspace_user.workspace_id, workspace_user.user_id
            )
            if existing is None:
                raise
            return existing

    async def disable_other_users_in_workspace(
        self, workspace_id: PydanticObjectId, user_id: PydanticObjectId
    ):
        for workspace_user in await self.get_workspace_users(workspace_id):
            if workspace_user.user_id != user_id and workspace_user.disable_for(
                DISABLED_BY_PLAN
            ):
                await self.upsert(workspace_user)

    async def enable_all_user_in_workspace(self, workspace_id: PydanticObjectId):
        enabled = 0
        for workspace_user in await self.get_workspace_users(workspace_id):
            if workspace_user.enable_for(DISABLED_BY_PLAN):
                await self.upsert(workspace_user)
                enabled += 1
        return enabled

    async def delete(self, workspace_id, user_id):
        workspace_user = await self.find_workspace_user(workspace_id, user_id)
        if not workspace_user:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="Resource doesn't exist"
            )
        return await self.delete_by_id(workspace_user.id)

    async def get_mine_workspaces(self, user_id: str):
        return await self.many(WorkspaceUserRow.user_id == _oid(user_id))

    async def delete_user_form_all_workspaces(self, user):
        return await self.delete_where(WorkspaceUserRow.user_id == _oid(user.id))

    async def delete_all_workspaces_users(self, workspaces_ids: List[PydanticObjectId]):
        return await self.delete_where(
            WorkspaceUserRow.workspace_id.in_([_oid(i) for i in workspaces_ids])
        )


class PostgresWorkspaceInvitationRepo(PostgresRepositoryBase):
    row = WorkspaceInviteRow
    document = WorkspaceUserInvitesDocument

    async def save(
        self, invitation: WorkspaceUserInvitesDocument
    ) -> WorkspaceUserInvitesDocument:
        return await self.upsert(invitation)

    async def _find(
        self, workspace_id, email
    ) -> Optional[WorkspaceUserInvitesDocument]:
        return await self.one(
            WorkspaceInviteRow.workspace_id == _oid(workspace_id),
            WorkspaceInviteRow.email == email,
        )

    async def create_workspace_invitation(
        self,
        workspace_id: PydanticObjectId,
        invitation: InvitationRequest,
        invited_by: Optional[str] = None,
    ):
        existing_invitation = await self._find(workspace_id, invitation.email)
        if existing_invitation:
            existing_invitation.invitation_status = InvitationStatus.PENDING
            existing_invitation.expiry = get_expiry_epoch_after(
                time_delta=timedelta(days=7)
            )
            existing_invitation.created_at = datetime.datetime.now(timezone.utc)
            existing_invitation.invitation_token = secrets.token_hex(16)
            # inviting again may change the role
            existing_invitation.role = invitation.role
            existing_invitation.invited_by = invited_by
        else:
            existing_invitation = WorkspaceUserInvitesDocument(
                workspace_id=workspace_id,
                email=invitation.email,
                role=invitation.role,
                invited_by=invited_by,
                invitation_token=secrets.token_hex(16),
                expiry=get_expiry_epoch_after(time_delta=timedelta(days=7)),
            )
        return await self.upsert(existing_invitation)

    async def get_workspace_invitations(self, workspace_id: PydanticObjectId):
        statuses = [InvitationStatus.PENDING.value, InvitationStatus.EXPIRED.value]
        stmt = (
            select(WorkspaceInviteRow.doc)
            .where(
                WorkspaceInviteRow.workspace_id == _oid(workspace_id),
                WorkspaceInviteRow.invitation_status.in_(statuses),
            )
            .order_by(*self._order())
        )
        async with self._session() as session:
            return await apaginate(
                session,
                stmt,
                transformer=lambda docs: [from_row_doc(self.document, d) for d in docs],
                unwrap_mode="unwrap",  # hand the transformer the doc column itself
                unique=False,  # JSONB rows are not hashable; the id is unique anyway
            )

    async def get_workspace_invitation_by_token(
        self, workspace_id: PydanticObjectId, invitation_token: str
    ) -> WorkspaceUserInvitesDocument | None:
        invitation_request = await self.one(
            WorkspaceInviteRow.invitation_token == invitation_token,
            WorkspaceInviteRow.workspace_id == _oid(workspace_id),
        )
        if not invitation_request:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content=MESSAGE_NOT_FOUND
            )
        return invitation_request

    async def delete_invitation_by_token_if_pending_state(self, invitation_token):
        invitation_request = await self.one(
            WorkspaceInviteRow.invitation_token == invitation_token
        )
        if not invitation_request:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Invitation not found")
        elif invitation_request.invitation_status == InvitationStatus.PENDING:
            await self.delete_by_id(invitation_request.id)
        else:
            raise HTTPException(
                HTTPStatus.UNPROCESSABLE_ENTITY, "Invitation not in pending state"
            )

    async def update_status_to_removed(
        self, workspace_id: PydanticObjectId, email: str
    ):
        invitation = await self._find(workspace_id, email)
        if invitation is not None:  # find_one(...).update() on no match is a no-op
            invitation.invitation_status = InvitationStatus.REMOVED
            await self.upsert(invitation)


class PostgresWorkspaceAPIKeyRepository(PostgresRepositoryBase):
    row = WorkspaceApiKeyRow
    document = WorkspaceAPIKeyDocument

    async def save(self, document: WorkspaceAPIKeyDocument) -> WorkspaceAPIKeyDocument:
        return await self.upsert(document)

    async def list_by_workspace(
        self, workspace_id: PydanticObjectId
    ) -> List[WorkspaceAPIKeyDocument]:
        return await self.many(WorkspaceApiKeyRow.workspace_id == _oid(workspace_id))

    async def get_or_404(self, key_id: PydanticObjectId) -> WorkspaceAPIKeyDocument:
        return await self.get_or_raise(key_id)

    async def find_by_key_hash(
        self, key_hash: str
    ) -> Optional[WorkspaceAPIKeyDocument]:
        return await self.one(WorkspaceApiKeyRow.key_hash == key_hash)


class PostgresWorkspaceDomainRepository(PostgresRepositoryBase):
    row = WorkspaceDomainRow
    document = WorkspaceDomainDocument

    async def create(
        self, document: WorkspaceDomainDocument
    ) -> WorkspaceDomainDocument:
        try:
            return await self.upsert(document)
        except IntegrityError:
            raise DomainAlreadyClaimed(document.domain)

    async def save(self, document: WorkspaceDomainDocument) -> WorkspaceDomainDocument:
        try:
            return await self.upsert(document)
        except IntegrityError:
            raise DomainVerifiedElsewhere(document.domain)

    async def get(self, domain_id) -> Optional[WorkspaceDomainDocument]:
        return await self.one(WorkspaceDomainRow.id == str(domain_id))

    async def list_by_workspace(
        self, workspace_id: PydanticObjectId
    ) -> List[WorkspaceDomainDocument]:
        return await self.many(
            WorkspaceDomainRow.workspace_id == _oid(workspace_id),
            order_by=(WorkspaceDomainRow.domain,),
        )

    async def count_by_workspace(self, workspace_id: PydanticObjectId) -> int:
        return await self.count(WorkspaceDomainRow.workspace_id == _oid(workspace_id))

    async def find_verified(self, domain: str) -> Optional[WorkspaceDomainDocument]:
        return await self.one(WorkspaceDomainRow.verified_domain == domain)

    async def list_due_for_recheck(
        self, checked_before: datetime.datetime, limit: int
    ) -> List[WorkspaceDomainDocument]:
        return await self.many(
            WorkspaceDomainRow.status == DomainStatus.VERIFIED.value,
            WorkspaceDomainRow.last_checked_at < checked_before,
            order_by=(WorkspaceDomainRow.last_checked_at, WorkspaceDomainRow.id),
            limit=limit,
        )

    async def delete(self, domain_id: PydanticObjectId) -> int:
        return await self.delete_by_id(domain_id)

    async def delete_by_workspace_ids(
        self, workspace_ids: List[PydanticObjectId]
    ) -> int:
        return await self.delete_where(
            WorkspaceDomainRow.workspace_id.in_([_oid(w) for w in workspace_ids])
        )


class PostgresSsoConnectionRepository(PostgresRepositoryBase):
    row = SsoConnectionRow
    document = SsoConnectionDocument

    async def create(self, document: SsoConnectionDocument) -> SsoConnectionDocument:
        try:
            return await self.upsert(document)
        except IntegrityError:
            raise SsoConnectionExists(document.polis_client_id)

    async def save(self, document: SsoConnectionDocument) -> SsoConnectionDocument:
        return await self.upsert(document)

    async def get(self, connection_id) -> Optional[SsoConnectionDocument]:
        return await self.one(SsoConnectionRow.id == str(connection_id))

    async def find_by_polis_client_id(
        self, client_id: str
    ) -> Optional[SsoConnectionDocument]:
        return await self.one(SsoConnectionRow.polis_client_id == client_id)

    async def list_by_workspace(
        self, workspace_id: PydanticObjectId
    ) -> List[SsoConnectionDocument]:
        return await self.many(SsoConnectionRow.workspace_id == _oid(workspace_id))

    async def count_by_workspace(self, workspace_id: PydanticObjectId) -> int:
        return await self.count(SsoConnectionRow.workspace_id == _oid(workspace_id))

    async def _enabled(self, workspace_id) -> List[SsoConnectionDocument]:
        enabled = await self.many(
            SsoConnectionRow.workspace_id == _oid(workspace_id),
            SsoConnectionRow.status == SsoConnectionStatus.ENABLED.value,
        )
        # latest enabled first, like the Mongo sort (enabled_at is not a spine
        # column; a workspace has at most a handful of connections)
        return sorted(
            enabled,
            key=lambda c: (
                c.enabled_at or datetime.datetime.min.replace(tzinfo=timezone.utc),
                str(c.id),
            ),
            reverse=True,
        )

    async def find_enabled(
        self, workspace_id: PydanticObjectId
    ) -> Optional[SsoConnectionDocument]:
        enabled = await self._enabled(workspace_id)
        return enabled[0] if enabled else None

    async def disable_others(
        self,
        workspace_id: PydanticObjectId,
        keep_id: PydanticObjectId,
        disabled_by: str,
        now: datetime.datetime,
    ) -> int:
        changed = 0
        for connection in await self._enabled(workspace_id):
            if str(connection.id) == str(keep_id):
                continue
            connection.status = SsoConnectionStatus.DISABLED
            connection.disabled_at = now
            connection.disabled_by = disabled_by
            connection.updated_at = now
            await self.upsert(connection)
            changed += 1
        return changed

    async def delete(self, connection_id: PydanticObjectId) -> int:
        return await self.delete_by_id(connection_id)

    async def delete_by_workspace_ids(
        self, workspace_ids: List[PydanticObjectId]
    ) -> int:
        return await self.delete_where(
            SsoConnectionRow.workspace_id.in_([_oid(w) for w in workspace_ids])
        )


class PostgresSsoUsedStateRepository(PostgresRepositoryBase):
    row = SsoUsedStateRow
    document = SsoUsedStateDocument

    async def claim(
        self, document: SsoUsedStateDocument, now: datetime.datetime
    ) -> SsoUsedStateDocument:
        # no TTL index here: expired records go on each claim
        await self.delete_where(SsoUsedStateRow.expires_at <= now)
        try:
            return await self.upsert(document)
        except IntegrityError:
            raise StateAlreadyUsed(document.nonce_hash)


class PostgresScimDirectoryRepository(PostgresRepositoryBase):
    row = ScimDirectoryRow
    document = ScimDirectoryDocument

    async def create(self, document: ScimDirectoryDocument) -> ScimDirectoryDocument:
        try:
            return await self.upsert(document)
        except IntegrityError:
            raise ScimDirectoryExists(str(document.workspace_id))

    async def save(self, document: ScimDirectoryDocument) -> ScimDirectoryDocument:
        return await self.upsert(document)

    async def update_fields(
        self, directory_id: PydanticObjectId, fields: Dict[str, Any]
    ) -> int:
        """The row is locked while ``fields`` are set on what is stored."""
        async with self._session() as session, session.begin():
            doc = (
                await session.execute(
                    select(ScimDirectoryRow.doc)
                    .where(ScimDirectoryRow.id == str(directory_id))
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                return 0
            stored = from_row_doc(ScimDirectoryDocument, doc)
            for name, value in fields.items():
                setattr(stored, name, value)
            await session.execute(self._upsert_statement(row_values(stored)))
        return 1

    async def get(self, directory_id) -> Optional[ScimDirectoryDocument]:
        return await self.one(ScimDirectoryRow.id == str(directory_id))

    async def find_by_workspace(
        self, workspace_id: PydanticObjectId
    ) -> Optional[ScimDirectoryDocument]:
        return await self.one(ScimDirectoryRow.workspace_id == _oid(workspace_id))

    async def list_all(self) -> List[ScimDirectoryDocument]:
        return await self.many(order_by=(ScimDirectoryRow.id,))

    async def delete(self, directory_id: PydanticObjectId) -> int:
        return await self.delete_by_id(directory_id)


class PostgresScimUserRepository(PostgresRepositoryBase):
    row = ScimUserRow
    document = ScimUserDocument

    async def save(self, document: ScimUserDocument) -> ScimUserDocument:
        return await self.upsert(document)

    async def get(self, scim_user_id) -> Optional[ScimUserDocument]:
        return await self.one(ScimUserRow.id == str(scim_user_id))

    async def find(
        self, directory_id: PydanticObjectId, polis_user_id: str
    ) -> Optional[ScimUserDocument]:
        return await self.one(
            ScimUserRow.directory_id == _oid(directory_id),
            ScimUserRow.polis_user_id == polis_user_id,
        )

    async def find_by_email(
        self, workspace_id: PydanticObjectId, email: str
    ) -> List[ScimUserDocument]:
        return await self.many(
            ScimUserRow.workspace_id == _oid(workspace_id), ScimUserRow.email == email
        )

    async def list_by_directory(
        self, directory_id: PydanticObjectId
    ) -> List[ScimUserDocument]:
        return await self.many(ScimUserRow.directory_id == _oid(directory_id))

    async def list_by_ids(self, ids: List[PydanticObjectId]) -> List[ScimUserDocument]:
        if not ids:
            return []
        return await self.many(ScimUserRow.id.in_([_oid(i) for i in ids]))

    async def delete_by_directory(self, directory_id: PydanticObjectId) -> int:
        return await self.delete_where(ScimUserRow.directory_id == _oid(directory_id))


class PostgresScimGroupRepository(PostgresRepositoryBase):
    row = ScimGroupRow
    document = ScimGroupDocument

    async def save(self, document: ScimGroupDocument) -> ScimGroupDocument:
        return await self.upsert(document)

    async def get(self, group_id) -> Optional[ScimGroupDocument]:
        return await self.one(ScimGroupRow.id == str(group_id))

    async def find(
        self, directory_id: PydanticObjectId, polis_group_id: str
    ) -> Optional[ScimGroupDocument]:
        return await self.one(
            ScimGroupRow.directory_id == _oid(directory_id),
            ScimGroupRow.polis_group_id == polis_group_id,
        )

    async def list_by_directory(
        self, directory_id: PydanticObjectId
    ) -> List[ScimGroupDocument]:
        return await self.many(ScimGroupRow.directory_id == _oid(directory_id))

    async def delete(self, group_id: PydanticObjectId) -> int:
        return await self.delete_by_id(group_id)

    async def delete_by_directory(self, directory_id: PydanticObjectId) -> int:
        return await self.delete_where(ScimGroupRow.directory_id == _oid(directory_id))


class PostgresScimGroupMemberRepository(PostgresRepositoryBase):
    row = ScimGroupMemberRow
    document = ScimGroupMemberDocument

    async def add(self, document: ScimGroupMemberDocument) -> ScimGroupMemberDocument:
        return await self.upsert(document)

    async def remove(
        self, group_id: PydanticObjectId, scim_user_id: PydanticObjectId
    ) -> int:
        return await self.delete_where(
            ScimGroupMemberRow.group_id == _oid(group_id),
            ScimGroupMemberRow.scim_user_id == _oid(scim_user_id),
        )

    async def list_by_user(
        self, scim_user_id: PydanticObjectId
    ) -> List[ScimGroupMemberDocument]:
        return await self.many(ScimGroupMemberRow.scim_user_id == _oid(scim_user_id))

    async def list_by_group(
        self, group_id: PydanticObjectId
    ) -> List[ScimGroupMemberDocument]:
        return await self.many(ScimGroupMemberRow.group_id == _oid(group_id))

    async def list_by_directory(
        self, directory_id: PydanticObjectId
    ) -> List[ScimGroupMemberDocument]:
        return await self.many(ScimGroupMemberRow.directory_id == _oid(directory_id))

    async def delete_by_group(self, group_id: PydanticObjectId) -> int:
        return await self.delete_where(ScimGroupMemberRow.group_id == _oid(group_id))

    async def delete_by_user(self, scim_user_id: PydanticObjectId) -> int:
        return await self.delete_where(
            ScimGroupMemberRow.scim_user_id == _oid(scim_user_id)
        )

    async def delete_by_directory(self, directory_id: PydanticObjectId) -> int:
        return await self.delete_where(
            ScimGroupMemberRow.directory_id == _oid(directory_id)
        )


class PostgresScimEventRepository(PostgresRepositoryBase):
    row = ScimEventRow
    document = ScimEventDocument

    async def claim(
        self, document: ScimEventDocument, now: datetime.datetime
    ) -> ScimEventDocument:
        # no TTL index here: expired records go on each claim
        await self.delete_where(ScimEventRow.expires_at <= now)
        try:
            return await self.upsert(document)
        except IntegrityError:
            raise ScimEventSeen(document.event_key)

    async def release(self, event_key: str) -> int:
        return await self.delete_where(ScimEventRow.event_key == event_key)


class PostgresSessionRepository(PostgresRepositoryBase):
    row = SessionRow
    document = SessionDocument

    async def save(self, document: SessionDocument) -> SessionDocument:
        return await self.upsert(document)

    async def get(self, session_id: str) -> Optional[SessionDocument]:
        try:
            session_id = str(PydanticObjectId(session_id))
        except Exception:  # noqa: BLE001 — not an ObjectId: no such session
            return None
        return await self.one(SessionRow.id == session_id)

    async def list_active_by_user(self, user_id: str) -> List[SessionDocument]:
        return await self.many(
            SessionRow.user_id == user_id,
            SessionRow.revoked_at.is_(None),
            order_by=(SessionRow.created_at.desc(), SessionRow.id.desc()),
        )

    async def _update_live(self, change, *where) -> List[SessionDocument]:
        """Lock the live sessions matching ``where``, apply ``change`` to each
        and store them, in one transaction (the twin of a conditional
        ``$set``)."""
        async with self._session() as session, session.begin():
            docs = (
                (
                    await session.execute(
                        select(SessionRow.doc)
                        .where(SessionRow.revoked_at.is_(None), *where)
                        .order_by(SessionRow.created_at, SessionRow.id)
                        .with_for_update()
                    )
                )
                .scalars()
                .all()
            )
            stored = []
            for doc in docs:
                document = from_row_doc(SessionDocument, doc)
                change(document)
                await session.execute(self._upsert_statement(row_values(document)))
                stored.append(document)
        return stored

    async def rotate(
        self,
        session_id: str,
        expected_jti: str,
        new_jti: str,
        now: datetime.datetime,
        expires_at: datetime.datetime,
    ) -> Optional[SessionDocument]:
        if await self.get(session_id) is None:
            return None

        def change(document: SessionDocument) -> None:
            document.previous_refresh_jti = document.refresh_jti
            document.refresh_jti = new_jti
            document.rotated_at = now
            document.last_refreshed_at = now
            document.expires_at = expires_at
            document.updated_at = now

        stored = await self._update_live(
            change,
            SessionRow.id == str(session_id),
            SessionRow.refresh_jti == expected_jti,
        )
        return stored[0] if stored else None

    async def touch(self, session_id: str, now: datetime.datetime) -> int:
        if await self.get(session_id) is None:
            return 0

        def change(document: SessionDocument) -> None:
            document.last_refreshed_at = now
            document.updated_at = now

        return len(await self._update_live(change, SessionRow.id == str(session_id)))

    @staticmethod
    def _revoker(reason: str, now: datetime.datetime):
        def change(document: SessionDocument) -> None:
            document.revoked_at = now
            document.revoke_reason = reason
            document.updated_at = now

        return change

    async def revoke(self, session_id: str, reason: str, now: datetime.datetime) -> int:
        if await self.get(session_id) is None:
            return 0
        return len(
            await self._update_live(
                self._revoker(reason, now), SessionRow.id == str(session_id)
            )
        )

    async def delete_expired(self, now: datetime.datetime) -> int:
        return await self.delete_where(SessionRow.expires_at <= now)

    async def delete_all_for_user(self, user_id: str) -> int:
        return await self.delete_where(SessionRow.user_id == user_id)

    async def revoke_all_for_user(
        self,
        user_id: str,
        reason: str,
        now: datetime.datetime,
        except_session_id: Optional[str] = None,
    ) -> int:
        where = [SessionRow.user_id == user_id]
        if except_session_id:
            where.append(SessionRow.id != str(except_session_id))
        return len(await self._update_live(self._revoker(reason, now), *where))


class PostgresUserTagsRepository(PostgresRepositoryBase):
    row = UserTagsRow
    document = UserTagsDocument

    # BaseRepository stubs, unused — kept so both stores expose the same surface.
    async def get(self, item_id, provider):
        pass

    async def add(self, item):
        pass

    async def update(self, item_id, item):
        pass

    async def delete(self, item_id, provider):
        pass

    async def get_tags_by_id(self, user_id: str):
        return await self.one(UserTagsRow.user_id == _oid(PydanticObjectId(user_id)))

    async def list(self, **kwargs) -> List[UserTagsDocument]:
        return await self.many()

    async def insert_user_tag(self, user_id: str, tag: UserTagType) -> UserTagsDocument:
        user_id = PydanticObjectId(user_id)
        user_tags = await self.one(UserTagsRow.user_id == _oid(user_id))
        if user_tags is None:
            user_tags = UserTagsDocument(user_id=user_id, tags=[tag])
        elif tag not in user_tags.tags:  # $addToSet
            user_tags.tags.append(tag)
        return await self.upsert(user_tags)
