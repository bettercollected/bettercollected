from typing import List

from beanie import PydanticObjectId
from common.models.user import User

from backend.app.schemas.action_document import ParameterValue, ActionDocument


class ActionRepository:

    async def create_action(self, name: str, action_code: str, user: User, parameters: List[ParameterValue]):
        new_action = ActionDocument(name=name, action_code=action_code, created_by=PydanticObjectId(user.id),
                                    parameters=parameters)
        return await new_action.save()

    async def delete_action(self, action_id: PydanticObjectId):
        await ActionDocument.find_one(ActionDocument.id == action_id).delete()
        return action_id

    async def get_all_actions(self):
        return await ActionDocument.find().to_list()

    async def get_action_by_id(self, action_id: PydanticObjectId):
        return await ActionDocument.find_one(ActionDocument.id == action_id)

    async def get_actions_by_ids(self, action_ids: List[PydanticObjectId]):
        return await ActionDocument.find({"_id": {"$in": action_ids}}).to_list()
