from typing import List

from beanie import PydanticObjectId
from common.models.user import User

from backend.app.models.dtos.action_dto import ActionDto
from backend.app.schemas.action_document import ActionDocument


class ActionRepository:

    async def create_action(self, workspace_id: PydanticObjectId, action: ActionDto, user: User):
        new_action = ActionDocument(**action.dict(), created_by=PydanticObjectId(user.id), workspace_id=workspace_id)
        return await new_action.save()

    async def delete_action(self, action_id: PydanticObjectId):
        await ActionDocument.find_one(ActionDocument.id == action_id).delete()
        return action_id

    async def get_all_actions(self, workspace_id: PydanticObjectId, public_only=True):
        if public_only:
            return await ActionDocument.find({"workspace_id": workspace_id, "settings.is_public": True}).to_list()
        return await ActionDocument.find({"workspace_id": workspace_id}).to_list()

    async def get_action_by_id(self, workspace_id: PydanticObjectId, action_id: PydanticObjectId, public_only=True):
        if public_only:
            return await ActionDocument.find_one(
                ActionDocument.id == action_id and ActionDocument.workspace_id == workspace_id and
                ActionDocument.settings.is_public == True)
        return await ActionDocument.find_one(
            ActionDocument.id == action_id and ActionDocument.workspace_id == workspace_id)

    async def get_actions_by_ids(self, workspace_id: PydanticObjectId, action_ids: List[PydanticObjectId]):
        return await ActionDocument.find({"_id": {"$in": action_ids}, "workspace_id": workspace_id}).to_list()
