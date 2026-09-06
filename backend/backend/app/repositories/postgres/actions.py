"""Postgres twin of the actions-group repository."""

from typing import List

from beanie import PydanticObjectId

from backend.app.models.dtos.action_dto import ActionDto
from backend.app.repositories.postgres.forms import _oid
from backend.app.schemas.action_document import ActionDocument, WorkspaceActionsDocument
from backend.db.models import ActionRow, WorkspaceActionRow
from common.configs.crypto import Crypto
from common.db import PostgresRepositoryBase
from common.models.user import User


class PostgresActionRepository(PostgresRepositoryBase):
    row = ActionRow
    document = ActionDocument

    def __init__(self, session_factory, crypto: Crypto):
        super().__init__(session_factory)
        self.crypto = crypto

    async def create_action(
        self, workspace_id: PydanticObjectId, action: ActionDto, user: User
    ) -> ActionDocument:
        if action.secrets is not None:
            for secret in action.secrets:
                secret.value = self.crypto.encrypt(secret.value)
        return await self.upsert(
            ActionDocument(
                **action.model_dump(mode="json"),
                created_by=PydanticObjectId(user.id),
                workspace_id=workspace_id,
            )
        )

    async def delete_action(self, action_id: PydanticObjectId):
        await self.delete_by_id(action_id)
        return action_id

    async def get_all_actions(self):
        return await self.many()

    async def get_action_by_id(self, action_id: PydanticObjectId):
        return await self.one(ActionRow.id == _oid(action_id))

    async def get_workspace_action(
        self, workspace_id: PydanticObjectId, action_id: PydanticObjectId
    ) -> WorkspaceActionsDocument | None:
        return await self.one_of(
            WorkspaceActionRow,
            WorkspaceActionsDocument,
            WorkspaceActionRow.workspace_id == _oid(workspace_id),
            WorkspaceActionRow.action_id == _oid(action_id),
        )

    async def get_actions_by_ids(self, action_ids: List[PydanticObjectId]):
        return await self.many(ActionRow.id.in_([_oid(i) for i in action_ids]))

    async def create_action_in_workspace_from_action(
        self,
        workspace_id: PydanticObjectId,
        action_id: PydanticObjectId,
        credentials: str = None,
    ):
        workspace_action = await self.get_workspace_action(workspace_id, action_id)
        secrets = None
        if credentials:
            secrets = [{"name": "Credentials", "value": credentials}]
        if workspace_action is None:
            workspace_action = WorkspaceActionsDocument(
                workspace_id=workspace_id, action_id=action_id
            )
        workspace_action.secrets = secrets
        return await self.upsert(workspace_action, row=WorkspaceActionRow)

    async def create_global_action(self, action: ActionDto, user: User):
        if action.secrets is not None:
            for secret in action.secrets:
                secret.value = self.crypto.encrypt(secret.value)
        return await self.upsert(
            ActionDocument(
                **action.model_dump(mode="json"), created_by=PydanticObjectId(user.id)
            )
        )
