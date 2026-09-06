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

from backend.app.exceptions import HTTPException
from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.models.invitation_request import InvitationRequest
from backend.app.schemas.blacklisted_refresh_tokens import BlackListedRefreshTokens
from backend.app.schemas.user_tags import UserTagsDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_api_key import WorkspaceAPIKeyDocument
from backend.app.schemas.workspace_invitation import WorkspaceUserInvitesDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.auth_cookie_service import get_expiry_epoch_after
from backend.db.base import SCHEMA
from backend.db.models import (
    BlacklistedRefreshTokenRow,
    UserTagsRow,
    WorkspaceApiKeyRow,
    WorkspaceInviteRow,
    WorkspaceRow,
    WorkspaceUserRow,
)
from common.constants import MESSAGE_NOT_FOUND
from common.db import (
    PostgresRepositoryBase,
    from_canonical_document,
    from_row_doc,
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

    async def disable_other_users_in_workspace(
        self, workspace_id: PydanticObjectId, user_id: PydanticObjectId
    ):
        for workspace_user in await self.get_workspace_users(workspace_id):
            if workspace_user.user_id != user_id:
                workspace_user.disabled = True
                await self.upsert(workspace_user)

    async def enable_all_user_in_workspace(self, workspace_id: PydanticObjectId):
        workspace_users = await self.get_workspace_users(workspace_id)
        for workspace_user in workspace_users:
            workspace_user.disabled = False
        await self.upsert_many(workspace_users)
        return len(workspace_users)

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
        self, workspace_id: PydanticObjectId, invitation: InvitationRequest
    ):
        existing_invitation = await self._find(workspace_id, invitation.email)
        if existing_invitation:
            existing_invitation.invitation_status = InvitationStatus.PENDING
            existing_invitation.expiry = get_expiry_epoch_after(
                time_delta=timedelta(days=7)
            )
            existing_invitation.created_at = datetime.datetime.now(timezone.utc)
            existing_invitation.invitation_token = secrets.token_hex(16)
        else:
            existing_invitation = WorkspaceUserInvitesDocument(
                workspace_id=workspace_id,
                email=invitation.email,
                role=invitation.role,
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


class PostgresBlacklistedRefreshTokenRepository(PostgresRepositoryBase):
    row = BlacklistedRefreshTokenRow
    document = BlackListedRefreshTokens

    async def find_by_token(self, token: str) -> Optional[BlackListedRefreshTokens]:
        return await self.one(BlacklistedRefreshTokenRow.token == token)

    async def add(self, token: str, expiry) -> BlackListedRefreshTokens:
        return await self.upsert(BlackListedRefreshTokens(token=token, expiry=expiry))


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
