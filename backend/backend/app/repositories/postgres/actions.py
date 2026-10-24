"""The actions group's repository: Postgres only (its Mongo collections are
read only by the import from 4.0)."""

from typing import List

from backend.app.models.dtos.action_dto import ActionDto
from backend.app.schemas.action_document import ActionDocument, WorkspaceActionsDocument
from backend.db.models import ActionRow, WorkspaceActionRow
from common.configs.crypto import Crypto
from common.models.standard_form import ParameterValue
from common.models.user import User
from common.records import RecordId
from common.records.repository import RecordRepository


class PostgresActionRepository(RecordRepository):
    """Actions (``actions``) and each workspace's copy of one, with the
    credentials it configured (``workspace_actions``)."""

    row = ActionRow
    document = ActionDocument

    def __init__(self, session_factory, crypto: Crypto):
        super().__init__(session_factory)
        self.crypto = crypto

    def _encrypt_secrets(self, action: ActionDto) -> None:
        if action.secrets is not None:
            for secret in action.secrets:
                secret.value = self.crypto.encrypt(secret.value)

    async def create_action(
        self, workspace_id: RecordId, action: ActionDto, user: User
    ) -> ActionDocument:
        self._encrypt_secrets(action)
        return await self.save_document(
            ActionDocument(
                **action.model_dump(mode="json"),
                created_by=RecordId(user.id),
                workspace_id=workspace_id,
            )
        )

    async def delete_action(self, action_id: RecordId):
        await self.delete_by_id(action_id)
        # each workspace's copy of the action (with its credentials) goes too
        await self.delete_where(
            WorkspaceActionRow.action_id == str(action_id), row=WorkspaceActionRow
        )
        return action_id

    async def get_all_actions(self) -> List[ActionDocument]:
        return await self.many()

    async def get_action_by_id(self, action_id: RecordId):
        return await self.one(ActionRow.id == str(action_id))

    async def get_workspace_action(
        self, workspace_id: RecordId, action_id: RecordId
    ) -> WorkspaceActionsDocument | None:
        return await self.one_of(
            WorkspaceActionRow,
            WorkspaceActionsDocument,
            WorkspaceActionRow.workspace_id == str(workspace_id),
            WorkspaceActionRow.action_id == str(action_id),
        )

    async def get_actions_by_ids(
        self, action_ids: List[RecordId]
    ) -> List[ActionDocument]:
        return await self.many(ActionRow.id.in_([str(i) for i in action_ids]))

    async def create_action_in_workspace_from_action(
        self,
        workspace_id: RecordId,
        action_id: RecordId,
        credentials: str = None,
    ) -> WorkspaceActionsDocument:
        """The workspace's copy of the action, created or updated in place,
        holding ``credentials`` (already encrypted) or none."""
        workspace_action = await self.get_workspace_action(workspace_id, action_id)
        secrets = None
        if credentials:
            secrets = [ParameterValue(name="Credentials", value=credentials)]
        if workspace_action is None:
            workspace_action = WorkspaceActionsDocument(
                workspace_id=workspace_id, action_id=action_id
            )
        workspace_action.secrets = secrets
        return await self.save_document(workspace_action, row=WorkspaceActionRow)

    async def create_global_action(self, action: ActionDto, user: User):
        self._encrypt_secrets(action)
        return await self.save_document(
            ActionDocument(**action.model_dump(mode="json"), created_by=RecordId(user.id))
        )
