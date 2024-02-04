from typing import List

from beanie import PydanticObjectId
from common.configs.crypto import Crypto
from common.models.user import User

from backend.app.models.dtos.action_dto import ActionDto, ActionResponse
from backend.app.schemas.action_document import ActionDocument, WorkspaceActionsDocument
from backend.app.schemas.standard_form import FormDocument


class ActionRepository:

    def __init__(self, crypto: Crypto):
        self.crypto = crypto

    async def create_action(self, workspace_id: PydanticObjectId, action: ActionDto, user: User):
        if action.secrets is not None:
            for secret in action.secrets:
                secret.value = self.crypto.encrypt(secret.value)
        new_action = ActionDocument(**action.dict(), created_by=PydanticObjectId(user.id), workspace_id=workspace_id)
        new_action = await new_action.save()
        return ActionResponse(**new_action.dict())

    async def delete_action(self, action_id: PydanticObjectId):
        await ActionDocument.find_one(ActionDocument.id == action_id).delete()
        return action_id

    async def get_all_actions(self):
        return await ActionDocument.find().to_list()

    async def get_action_by_id(self, action_id: PydanticObjectId):
        return await ActionDocument.find_one(ActionDocument.id == action_id)

    # query = {
    #     '_id': action_id,
    #     'workspace_id': workspace_id,
    # }
    # if public_only:
    #     query["settings.is_public"] = True
    # action = await ActionDocument.find(query).aggregate([
    #     {
    #         '$lookup': {
    #             'from': 'action_code',
    #             'localField': 'action_code_id',
    #             'foreignField': '_id',
    #             'as': 'action_code'
    #         }
    #     },
    #     {
    #         "$set": {
    #             "action_code": "$action_code.action_code"
    #         }
    #     },
    #     {
    #         '$unwind': {
    #             'path': '$action_code',
    #             'preserveNullAndEmptyArrays': True
    #         }
    #     },
    #     {
    #         '$limit': 1
    #     }
    # ]).to_list()
    # if len(action) == 0:
    #     return None
    # else:
    #     action = action[0]
    # return ActionResponse(**action, id=action["_id"])

    async def get_actions_by_ids(self, action_ids: List[PydanticObjectId]):
        return await ActionDocument.find({"_id": {"$in": action_ids}}).to_list()
        # actions = await ActionDocument.find({"_id": {"$in": action_ids}, "workspace_id": workspace_id}).aggregate([
        #     {
        #         '$lookup': {
        #             'from': 'action_code',
        #             'localField': 'action_code_id',
        #             'foreignField': '_id',
        #             'as': 'action_code'
        #         }
        #     },
        #     {
        #         "$set": {
        #             "action_code": "$action_code.action_code"
        #         }
        #     },
        #     {
        #         '$unwind': {
        #             'path': '$action_code',
        #             'preserveNullAndEmptyArrays': True
        #         }
        #     }
        # ]).to_list()
        #
        # return [ActionResponse(**action, id=action["_id"]) for action in actions]

    # TODO resolve circular deps with action_service and workspace_form_service and update in workspace form repo
    async def remove_action_form_all_forms(self, action_id: PydanticObjectId):
        await FormDocument.find(
            {
                "$or":
                    [
                        {
                            "actions.on_submit": {"$in": [action_id]}
                        },
                        {
                            "actions.on_open": {"$in": [action_id]}
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

    async def create_action_in_workspace_from_action(self, workspace_id: PydanticObjectId, action_id: PydanticObjectId,
                                                     credentials: str = None,
                                                     ):
        workspace_action = await WorkspaceActionsDocument.find_one(
            {"workspace_id": workspace_id, "action_id": action_id})
        secrets = None
        if credentials:
            secrets = [{'name': 'Credentials',
                        'value': credentials}]
        if workspace_action is None:
            workspace_action = WorkspaceActionsDocument(workspace_id=workspace_id, action_id=action_id,
                                                              )
        workspace_action.secrets = secrets
        await workspace_action.save()
        return workspace_action

    async def create_global_action(self, action: ActionDto, user: User):
        if action.secrets is not None:
            for secret in action.secrets:
                secret.value = self.crypto.encrypt(secret.value)
        return await ActionDocument(**action.dict(), created_by=PydanticObjectId(user.id)).save()
