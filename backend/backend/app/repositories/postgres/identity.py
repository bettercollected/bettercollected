"""The identity group's repositories: Postgres only (its Mongo collections are
read only by the import from 4.0, ``python -m backend.migrate``).

Workspaces, their members, invitations, API keys and email domains, single
sign-on connections and used sign-in states, the SCIM directory sync
collections, sessions and user tags. Queries use the spine columns of the
rows in :mod:`backend.db.models`; the documents are
:class:`common.records.Record` classes, encoded and decoded by
:mod:`common.records.codec`. The methods keep the behaviour of the 4.0 Mongo
repositories they replace, including their quirks (404 vs None, the
document layer's NotFoundError).

One method crosses a group boundary: ``get_workspace_with_action_by_id``
reads workspaces (identity) and workspace_actions (actions). In 4.0 Mongo
joined them with ``$lookup``; it composes the two reads through the actions
repository (:func:`with_workspace_action`). The forms group's Mongo
repositories, which still serve the forms group in the mongo and dual modes,
read workspaces through this group's repositories too (no join into
identity is left, see ``backend.db.groups.MONGO_JOINS``).
"""

import datetime
import secrets
from datetime import timedelta, timezone
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Tuple

from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import and_, func, not_, or_, select
from sqlalchemy.exc import IntegrityError

from backend.app.exceptions import HTTPException
from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.models.enum.workspace_roles import has_owner_role
from backend.app.models.invitation_request import InvitationRequest
from backend.app.repositories.metric_periods import (
    object_id_at,
    postgres_counts_per_period,
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
from common.records import (
    RecordId,
    decode,
    from_canonical_document,
    row_values,
    to_bson,
)
from common.records.repository import RecordRepository
from common.enums.workspace_invitation_status import InvitationStatus
from common.clock import utcnow


class SsoConnectionExists(Exception):
    """A connection with this Polis clientID is already recorded."""


class StateAlreadyUsed(Exception):
    """This sign-in's nonce was accepted before (a replayed callback)."""


class ScimDirectoryExists(Exception):
    """The workspace already has a directory (or the Polis id is taken)."""


class ScimEventSeen(Exception):
    """This event was accepted before (a retry or a replay)."""


class DomainAlreadyClaimed(Exception):
    """The workspace already has a claim for this domain."""


class DomainVerifiedElsewhere(Exception):
    """Another workspace holds this domain verified."""


def _oid(value: Any) -> str:
    """Spine ids are ObjectId hex strings; accept whatever the callers pass."""
    return str(value)


def _set_paths(target: Any, fields: Dict[str, Any]) -> None:
    """Apply ``{"a.b": value}`` to a model (attributes) or dict (keys)."""
    for path, value in fields.items():
        *parents, leaf = path.split(".")
        node: Any = target
        for part in parents:
            node = node[part] if isinstance(node, dict) else getattr(node, part)
        if isinstance(node, dict):
            node[leaf] = value
        else:
            setattr(node, leaf, value)


async def with_workspace_action(
    actions, workspace: Optional[Dict[str, Any]], workspace_id, action_id
) -> Dict[str, Any]:
    """``workspace`` (a stored workspace document, or ``None``) as the action
    runner gets it: ``parameters.<action_id>`` / ``secrets.<action_id>`` set
    from the workspace's copy of the action (read through ``actions``) and
    ``id`` set. 404 when there is no such workspace or copy. The shape of the
    4.0 ``$lookup`` aggregation."""
    workspace_action = (
        None
        if workspace is None
        else await actions.get_workspace_action(
            workspace_id=RecordId(str(workspace_id)),
            action_id=RecordId(str(action_id)),
        )
    )
    if workspace is None or workspace_action is None:
        raise HTTPException(status_code=404, content="Workspace not found")
    action = to_bson(workspace_action)
    for key in ("parameters", "secrets"):
        if key in action:  # $set of a missing path adds nothing
            workspace.setdefault(key, {})[str(action_id)] = action[key]
    workspace["id"] = RecordId(str(workspace_id))
    return workspace


class PostgresWorkspaceRepository(RecordRepository):
    row = WorkspaceRow
    document = WorkspaceDocument

    def __init__(self, session_factory, action_repository):
        super().__init__(session_factory)
        self._actions = action_repository

    # BaseRepository stubs, unused (the interface the services were typed with)
    async def list(self):
        pass

    async def get(self, item_id, provider):
        pass

    async def add(self, item):
        pass

    async def delete(self, item_id, provider):
        pass

    async def update(
        self, item_id: RecordId, item: WorkspaceDocument
    ) -> WorkspaceDocument:
        if await self.one(WorkspaceRow.id == _oid(item_id)) is None:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Workspace not found")
        return await self.save_document(item)

    async def get_workspace_by_id(
        self, workspace_id: RecordId
    ) -> WorkspaceDocument:
        workspace = await self.one(WorkspaceRow.id == _oid(workspace_id))
        if not workspace:
            raise HTTPException(HTTPStatus.NOT_FOUND)
        return workspace

    async def find_by_id(
        self, workspace_id: RecordId
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

    async def list_custom_domain_references(self) -> List[Tuple[str, str]]:
        # Mongo's {"custom_domain_disabled": {"$ne": true}}: only a JSON true excludes
        stmt = select(WorkspaceRow.custom_domain, WorkspaceRow.id).where(
            WorkspaceRow.custom_domain.is_not(None),
            WorkspaceRow.custom_domain != "",
            not_(WorkspaceRow.doc.contains({"custom_domain_disabled": True})),
        )
        async with self._session() as session:
            rows = (await session.execute(stmt)).all()
        return sorted(((domain, str(ws)) for domain, ws in rows), key=lambda row: row[1])

    async def get_or_404(self, workspace_id: RecordId) -> WorkspaceDocument:
        return await self.get_or_raise(workspace_id)

    async def save(self, workspace: WorkspaceDocument) -> WorkspaceDocument:
        return await self.save_document(workspace)

    async def set_fields(
        self, workspace: WorkspaceDocument, fields: Dict[str, Any]
    ) -> None:
        """Set ``fields`` (dotted paths) on the stored workspace, atomically:
        the row is locked while they are applied to the stored copy, so a
        concurrent change of other fields is kept (Mongo's partial ``$set``),
        never overwritten from ``workspace``, which may be stale. Then
        ``workspace`` is refreshed from what was stored (as Beanie's
        ``document.update`` did). A workspace that is not stored stays so."""
        async with self._session() as session, session.begin():
            doc = (
                await session.execute(
                    select(WorkspaceRow.doc)
                    .where(WorkspaceRow.id == _oid(workspace.id))
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                _set_paths(workspace, fields)
                return
            stored = decode(WorkspaceDocument, doc)
            _set_paths(stored, fields)
            await session.execute(self._upsert_statement(row_values(stored)))
        for name in type(stored).model_fields:
            setattr(workspace, name, getattr(stored, name))

    async def set_owner_if(
        self, workspace_id: RecordId, expected_owner_id: str, new_owner_id: str
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
            stored = decode(WorkspaceDocument, doc)
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

    async def get_workspace_by_ids(self, workspace_ids: List[RecordId]):
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

    async def delete_workspaces_with_ids(self, workspace_ids: List[RecordId]):
        return await self.delete_where(
            WorkspaceRow.id.in_([_oid(i) for i in workspace_ids])
        )

    async def get_workspace_with_action_by_id(
        self, workspace_id: RecordId, action_id: RecordId
    ):
        """The workspace with its copy of the action, read through the actions
        repository (``with_workspace_action``; see the module docstring)."""
        async with self._session() as session:
            raw = (
                await session.execute(
                    select(WorkspaceRow.doc).where(
                        WorkspaceRow.id == _oid(workspace_id)
                    )
                )
            ).scalar_one_or_none()
        return await with_workspace_action(
            self._actions,
            None if raw is None else from_canonical_document(raw),
            workspace_id,
            action_id,
        )


class PostgresWorkspaceUserRepository(RecordRepository):
    row = WorkspaceUserRow
    document = WorkspaceUserDocument

    async def get_workspace_users(self, workspace_id: RecordId):
        return await self.many(WorkspaceUserRow.workspace_id == _oid(workspace_id))

    async def find_workspace_user(
        self, workspace_id: RecordId, user_id: RecordId
    ) -> Optional[WorkspaceUserDocument]:
        return await self.one(
            WorkspaceUserRow.workspace_id == _oid(workspace_id),
            WorkspaceUserRow.user_id == _oid(user_id),
        )

    async def save(self, workspace_user: WorkspaceUserDocument):
        return await self.save_document(workspace_user)

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
        self, workspace_id: RecordId, user_id: RecordId
    ):
        for workspace_user in await self.get_workspace_users(workspace_id):
            if (
                workspace_user.user_id != user_id
                and not has_owner_role(workspace_user.roles)
                and workspace_user.disable_for(DISABLED_BY_PLAN)
            ):
                await self.save_document(workspace_user)

    async def enable_all_user_in_workspace(self, workspace_id: RecordId):
        enabled = 0
        for workspace_user in await self.get_workspace_users(workspace_id):
            if workspace_user.enable_for(DISABLED_BY_PLAN):
                await self.save_document(workspace_user)
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

    async def delete_all_workspaces_users(self, workspaces_ids: List[RecordId]):
        return await self.delete_where(
            WorkspaceUserRow.workspace_id.in_([_oid(i) for i in workspaces_ids])
        )


class PostgresWorkspaceInvitationRepo(RecordRepository):
    row = WorkspaceInviteRow
    document = WorkspaceUserInvitesDocument

    async def save(
        self, invitation: WorkspaceUserInvitesDocument
    ) -> WorkspaceUserInvitesDocument:
        return await self.save_document(invitation)

    async def _find(
        self, workspace_id, email
    ) -> Optional[WorkspaceUserInvitesDocument]:
        return await self.one(
            WorkspaceInviteRow.workspace_id == _oid(workspace_id),
            WorkspaceInviteRow.email == email,
        )

    async def create_workspace_invitation(
        self,
        workspace_id: RecordId,
        invitation: InvitationRequest,
        invited_by: Optional[str] = None,
    ):
        existing_invitation = await self._find(workspace_id, invitation.email)
        if existing_invitation:
            existing_invitation.invitation_status = InvitationStatus.PENDING
            existing_invitation.expiry = get_expiry_epoch_after(
                time_delta=timedelta(days=7)
            )
            existing_invitation.created_at = utcnow()
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
        return await self.save_document(existing_invitation)

    async def get_workspace_invitations(self, workspace_id: RecordId):
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
                transformer=lambda docs: [decode(self.document, d) for d in docs],
                unwrap_mode="unwrap",  # hand the transformer the doc column itself
                unique=False,  # JSONB rows are not hashable; the id is unique anyway
            )

    async def get_workspace_invitation_by_token(
        self, workspace_id: RecordId, invitation_token: str
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

    async def delete_invitation_by_token_if_pending_state(
        self, workspace_id: RecordId, invitation_token: str
    ):
        # Scoped to the workspace: a token from another workspace reads as
        # "not found", the same as a token that does not exist.
        invitation_request = await self.one(
            WorkspaceInviteRow.invitation_token == invitation_token,
            WorkspaceInviteRow.workspace_id == _oid(workspace_id),
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
        self, workspace_id: RecordId, email: str
    ):
        """Mark the invitation removed, atomically (Mongo's ``$set`` of the
        status): the row is locked and only its status changes, so a
        concurrent re-invitation's token and expiry are kept. No match: a
        no-op."""
        async with self._session() as session, session.begin():
            doc = (
                await session.execute(
                    select(WorkspaceInviteRow.doc)
                    .where(
                        WorkspaceInviteRow.workspace_id == _oid(workspace_id),
                        WorkspaceInviteRow.email == email,
                    )
                    .order_by(*self._order())
                    .limit(1)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                return
            invitation = decode(WorkspaceUserInvitesDocument, doc)
            invitation.invitation_status = InvitationStatus.REMOVED
            await session.execute(self._upsert_statement(row_values(invitation)))


class PostgresWorkspaceAPIKeyRepository(RecordRepository):
    row = WorkspaceApiKeyRow
    document = WorkspaceAPIKeyDocument

    async def save(self, document: WorkspaceAPIKeyDocument) -> WorkspaceAPIKeyDocument:
        return await self.save_document(document)

    async def list_by_workspace(
        self, workspace_id: RecordId
    ) -> List[WorkspaceAPIKeyDocument]:
        return await self.many(WorkspaceApiKeyRow.workspace_id == _oid(workspace_id))

    async def get_or_404(self, key_id: RecordId) -> WorkspaceAPIKeyDocument:
        return await self.get_or_raise(key_id)

    async def find_by_key_hash(
        self, key_hash: str
    ) -> Optional[WorkspaceAPIKeyDocument]:
        return await self.one(WorkspaceApiKeyRow.key_hash == key_hash)

    async def touch_last_used(self, key_id: RecordId, now: datetime.datetime) -> bool:
        """Record that the key was used at ``now``, changing nothing else, and
        only while it is not revoked: the row is locked and re-read, so a
        revocation (or any other change) made since the caller read the key
        is never written back. Whether the key was live and touched."""
        async with self._session() as session, session.begin():
            doc = (
                await session.execute(
                    select(WorkspaceApiKeyRow.doc)
                    .where(
                        WorkspaceApiKeyRow.id == _oid(key_id),
                        WorkspaceApiKeyRow.revoked.is_not(True),
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                return False
            stored = decode(WorkspaceAPIKeyDocument, doc)
            stored.last_used_at = now
            await session.execute(self._upsert_statement(row_values(stored)))
        return True


class PostgresWorkspaceDomainRepository(RecordRepository):
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
            return await self.save_document(document)
        except IntegrityError:
            raise DomainVerifiedElsewhere(document.domain)

    async def get(self, domain_id) -> Optional[WorkspaceDomainDocument]:
        return await self.one(WorkspaceDomainRow.id == str(domain_id))

    async def list_by_workspace(
        self, workspace_id: RecordId
    ) -> List[WorkspaceDomainDocument]:
        return await self.many(
            WorkspaceDomainRow.workspace_id == _oid(workspace_id),
            order_by=(WorkspaceDomainRow.domain,),
        )

    async def count_by_workspace(self, workspace_id: RecordId) -> int:
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

    async def delete(self, domain_id: RecordId) -> int:
        return await self.delete_by_id(domain_id)

    async def delete_by_workspace_ids(
        self, workspace_ids: List[RecordId]
    ) -> int:
        return await self.delete_where(
            WorkspaceDomainRow.workspace_id.in_([_oid(w) for w in workspace_ids])
        )


class PostgresSsoConnectionRepository(RecordRepository):
    row = SsoConnectionRow
    document = SsoConnectionDocument

    async def create(self, document: SsoConnectionDocument) -> SsoConnectionDocument:
        try:
            return await self.upsert(document)
        except IntegrityError:
            raise SsoConnectionExists(document.polis_client_id)

    async def save(self, document: SsoConnectionDocument) -> SsoConnectionDocument:
        return await self.save_document(document)

    async def get(self, connection_id) -> Optional[SsoConnectionDocument]:
        return await self.one(SsoConnectionRow.id == str(connection_id))

    async def find_by_polis_client_id(
        self, client_id: str
    ) -> Optional[SsoConnectionDocument]:
        return await self.one(SsoConnectionRow.polis_client_id == client_id)

    async def list_by_workspace(
        self, workspace_id: RecordId
    ) -> List[SsoConnectionDocument]:
        return await self.many(SsoConnectionRow.workspace_id == _oid(workspace_id))

    async def count_by_workspace(self, workspace_id: RecordId) -> int:
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
        self, workspace_id: RecordId
    ) -> Optional[SsoConnectionDocument]:
        enabled = await self._enabled(workspace_id)
        return enabled[0] if enabled else None

    async def disable_others(
        self,
        workspace_id: RecordId,
        keep_id: RecordId,
        disabled_by: str,
        now: datetime.datetime,
    ) -> int:
        """Disable the workspace's other enabled connections, atomically: their
        rows are locked and re-read, so only connections still enabled change
        and nothing else of theirs is overwritten (Mongo's ``update_many``
        with ``$set``)."""
        async with self._session() as session, session.begin():
            docs = (
                (
                    await session.execute(
                        select(SsoConnectionRow.doc)
                        .where(
                            SsoConnectionRow.workspace_id == _oid(workspace_id),
                            SsoConnectionRow.status
                            == SsoConnectionStatus.ENABLED.value,
                            SsoConnectionRow.id != str(keep_id),
                        )
                        .order_by(SsoConnectionRow.id)
                        .with_for_update()
                    )
                )
                .scalars()
                .all()
            )
            for doc in docs:
                connection = decode(SsoConnectionDocument, doc)
                connection.status = SsoConnectionStatus.DISABLED
                connection.disabled_at = now
                connection.disabled_by = disabled_by
                connection.updated_at = now
                await session.execute(self._upsert_statement(row_values(connection)))
        return len(docs)

    async def delete(self, connection_id: RecordId) -> int:
        return await self.delete_by_id(connection_id)

    async def mark_release_pending(
        self, workspace_ids: List[RecordId], now: datetime.datetime
    ) -> int:
        changed = 0
        for connection in await self.many(
            SsoConnectionRow.workspace_id.in_([_oid(w) for w in workspace_ids])
        ):
            if connection.status == SsoConnectionStatus.RELEASE_PENDING:
                continue
            connection.status = SsoConnectionStatus.RELEASE_PENDING
            connection.disabled_at = now
            connection.updated_at = now
            await self.upsert(connection)
            changed += 1
        return changed

    async def list_release_pending(self, limit: int) -> List[SsoConnectionDocument]:
        return await self.many(
            SsoConnectionRow.status == SsoConnectionStatus.RELEASE_PENDING.value,
            order_by=(SsoConnectionRow.updated_at, SsoConnectionRow.id),
            limit=limit,
        )

    async def touch_release_pending(
        self, workspace_ids: List[RecordId], now: datetime.datetime
    ) -> int:
        changed = 0
        for connection in await self.many(
            SsoConnectionRow.workspace_id.in_([_oid(w) for w in workspace_ids]),
            SsoConnectionRow.status == SsoConnectionStatus.RELEASE_PENDING.value,
        ):
            connection.updated_at = now
            await self.upsert(connection)
            changed += 1
        return changed

    async def delete_by_workspace_ids(
        self, workspace_ids: List[RecordId]
    ) -> int:
        return await self.delete_where(
            SsoConnectionRow.workspace_id.in_([_oid(w) for w in workspace_ids])
        )


class PostgresSsoUsedStateRepository(RecordRepository):
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


class PostgresScimDirectoryRepository(RecordRepository):
    row = ScimDirectoryRow
    document = ScimDirectoryDocument

    async def create(self, document: ScimDirectoryDocument) -> ScimDirectoryDocument:
        try:
            return await self.upsert(document)
        except IntegrityError:
            raise ScimDirectoryExists(str(document.workspace_id))

    async def save(self, document: ScimDirectoryDocument) -> ScimDirectoryDocument:
        return await self.save_document(document)

    async def update_fields(
        self, directory_id: RecordId, fields: Dict[str, Any]
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
            stored = decode(ScimDirectoryDocument, doc)
            for name, value in fields.items():
                setattr(stored, name, value)
            await session.execute(self._upsert_statement(row_values(stored)))
        return 1

    async def get(self, directory_id) -> Optional[ScimDirectoryDocument]:
        return await self.one(ScimDirectoryRow.id == str(directory_id))

    async def find_by_workspace(
        self, workspace_id: RecordId
    ) -> Optional[ScimDirectoryDocument]:
        return await self.one(ScimDirectoryRow.workspace_id == _oid(workspace_id))

    async def list_all(self) -> List[ScimDirectoryDocument]:
        return await self.many(order_by=(ScimDirectoryRow.id,))

    async def delete(self, directory_id: RecordId) -> int:
        return await self.delete_by_id(directory_id)


class PostgresScimUserRepository(RecordRepository):
    row = ScimUserRow
    document = ScimUserDocument

    async def save(self, document: ScimUserDocument) -> ScimUserDocument:
        return await self.save_document(document)

    async def get(self, scim_user_id) -> Optional[ScimUserDocument]:
        return await self.one(ScimUserRow.id == str(scim_user_id))

    async def find(
        self, directory_id: RecordId, polis_user_id: str
    ) -> Optional[ScimUserDocument]:
        return await self.one(
            ScimUserRow.directory_id == _oid(directory_id),
            ScimUserRow.polis_user_id == polis_user_id,
        )

    async def find_by_email(
        self, workspace_id: RecordId, email: str
    ) -> List[ScimUserDocument]:
        return await self.many(
            ScimUserRow.workspace_id == _oid(workspace_id), ScimUserRow.email == email
        )

    async def list_by_directory(
        self, directory_id: RecordId
    ) -> List[ScimUserDocument]:
        return await self.many(ScimUserRow.directory_id == _oid(directory_id))

    async def list_by_ids(self, ids: List[RecordId]) -> List[ScimUserDocument]:
        if not ids:
            return []
        return await self.many(ScimUserRow.id.in_([_oid(i) for i in ids]))

    async def delete_by_directory(self, directory_id: RecordId) -> int:
        return await self.delete_where(ScimUserRow.directory_id == _oid(directory_id))


class PostgresScimGroupRepository(RecordRepository):
    row = ScimGroupRow
    document = ScimGroupDocument

    async def save(self, document: ScimGroupDocument) -> ScimGroupDocument:
        return await self.save_document(document)

    async def get(self, group_id) -> Optional[ScimGroupDocument]:
        return await self.one(ScimGroupRow.id == str(group_id))

    async def find(
        self, directory_id: RecordId, polis_group_id: str
    ) -> Optional[ScimGroupDocument]:
        return await self.one(
            ScimGroupRow.directory_id == _oid(directory_id),
            ScimGroupRow.polis_group_id == polis_group_id,
        )

    async def list_by_directory(
        self, directory_id: RecordId
    ) -> List[ScimGroupDocument]:
        return await self.many(ScimGroupRow.directory_id == _oid(directory_id))

    async def delete(self, group_id: RecordId) -> int:
        return await self.delete_by_id(group_id)

    async def delete_by_directory(self, directory_id: RecordId) -> int:
        return await self.delete_where(ScimGroupRow.directory_id == _oid(directory_id))


class PostgresScimGroupMemberRepository(RecordRepository):
    row = ScimGroupMemberRow
    document = ScimGroupMemberDocument

    async def add(self, document: ScimGroupMemberDocument) -> ScimGroupMemberDocument:
        return await self.save_document(document)

    async def remove(
        self, group_id: RecordId, scim_user_id: RecordId
    ) -> int:
        return await self.delete_where(
            ScimGroupMemberRow.group_id == _oid(group_id),
            ScimGroupMemberRow.scim_user_id == _oid(scim_user_id),
        )

    async def list_by_user(
        self, scim_user_id: RecordId
    ) -> List[ScimGroupMemberDocument]:
        return await self.many(ScimGroupMemberRow.scim_user_id == _oid(scim_user_id))

    async def list_by_group(
        self, group_id: RecordId
    ) -> List[ScimGroupMemberDocument]:
        return await self.many(ScimGroupMemberRow.group_id == _oid(group_id))

    async def list_by_directory(
        self, directory_id: RecordId
    ) -> List[ScimGroupMemberDocument]:
        return await self.many(ScimGroupMemberRow.directory_id == _oid(directory_id))

    async def delete_by_group(self, group_id: RecordId) -> int:
        return await self.delete_where(ScimGroupMemberRow.group_id == _oid(group_id))

    async def delete_by_user(self, scim_user_id: RecordId) -> int:
        return await self.delete_where(
            ScimGroupMemberRow.scim_user_id == _oid(scim_user_id)
        )

    async def delete_by_directory(self, directory_id: RecordId) -> int:
        return await self.delete_where(
            ScimGroupMemberRow.directory_id == _oid(directory_id)
        )


class PostgresScimEventRepository(RecordRepository):
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


class PostgresSessionRepository(RecordRepository):
    row = SessionRow
    document = SessionDocument

    async def save(self, document: SessionDocument) -> SessionDocument:
        return await self.save_document(document)

    async def get(self, session_id: str) -> Optional[SessionDocument]:
        try:
            session_id = str(RecordId(session_id))
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
                document = decode(SessionDocument, doc)
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


class PostgresUserTagsRepository(RecordRepository):
    row = UserTagsRow
    document = UserTagsDocument

    # BaseRepository stubs, unused (the interface the services were typed with)
    async def get(self, item_id, provider):
        pass

    async def add(self, item):
        pass

    async def update(self, item_id, item):
        pass

    async def delete(self, item_id, provider):
        pass

    async def get_tags_by_id(self, user_id: str):
        return await self.one(UserTagsRow.user_id == _oid(RecordId(user_id)))

    async def list(self, **kwargs) -> List[UserTagsDocument]:
        return await self.many()

    async def insert_user_tag(self, user_id: str, tag: UserTagType) -> UserTagsDocument:
        user_id = RecordId(user_id)
        user_tags = await self.one(UserTagsRow.user_id == _oid(user_id))
        if user_tags is None:
            user_tags = UserTagsDocument(user_id=user_id, tags=[tag])
        elif tag not in user_tags.tags:  # $addToSet
            user_tags.tags.append(tag)
        return await self.upsert(user_tags)
