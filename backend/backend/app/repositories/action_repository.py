from typing import List

from beanie import PydanticObjectId
from common.configs.crypto import Crypto
from common.models.user import User

from backend.app.models.dtos.action_dto import ActionDto
from backend.app.schemas.action_document import ActionDocument
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument


class ActionRepository:

    def __init__(self, crypto: Crypto):
        self.crypto = crypto

    async def create_action(self, workspace_id: PydanticObjectId, action: ActionDto, user: User):
        if action.secrets is not None:
            for secret in action.secrets:
                secret.value = self.crypto.encrypt(secret.value)
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
                ActionDocument.settings.is_public)
        return await ActionDocument.find_one(
            ActionDocument.id == action_id and ActionDocument.workspace_id == workspace_id)

    async def get_actions_by_ids(self, workspace_id: PydanticObjectId, action_ids: List[PydanticObjectId]):
        return await ActionDocument.find({"_id": {"$in": action_ids}, "workspace_id": workspace_id}).to_list()

    # TODO resolve circular deps with action_service and workspace_form_service and update in workspace form repo
    async def remove_action_form_all_forms(self, workspace_id, action_id: PydanticObjectId):
        form_ids = await WorkspaceFormDocument.find({"workspace_id": workspace_id}).aggregate([
            {
                "project": {
                    "form_id": 1,
                    "_id": 0
                }
            }
        ]).to_list()
        form_ids = [form.form_id for form in form_ids]
        await FormDocument.find(
            {"form_id": {"$in": form_ids},
             "$or":
                 [
                     {
                         "actions.on_submit": {"$in": [action_id]}
                     }
                 ]
             }).update(
            {
                "$pull": {"actions.on_submit": action_id},
                "$unset": {
                    f"parameters.{str(action_id)}": "",
                    f"secrets.{str(action_id)}": ""
                }
            })
