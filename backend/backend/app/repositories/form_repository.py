from typing import List

from beanie import PydanticObjectId

from backend.app.schemas.standard_form import FormDocument


class FormRepository:
    async def get_forms_in_workspace(
        self, workspace_id: PydanticObjectId, form_id_list: List[str]
    ):
        return (
            await FormDocument.find({"formId": {"$in": form_id_list}})
            .aggregate(
                [
                    {
                        "$lookup": {
                            "from": "workspaceForms",
                            "localField": "formId",
                            "foreignField": "formId",
                            "as": "workspaceForm",
                        }
                    },
                    {"$unwind": "$workspaceForm"},
                    {"$match": {"workspaceForm.workspaceId": workspace_id}},
                    {"$set": {"settings": "$workspaceForm.settings"}},
                ]
            )
            .to_list()
        )
