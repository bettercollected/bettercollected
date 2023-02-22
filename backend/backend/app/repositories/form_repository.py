from typing import List

from beanie import PydanticObjectId

from backend.app.schemas.standard_form import FormDocument


class FormRepository:
    async def get_forms_in_workspace(
        self, workspace_id: PydanticObjectId, form_id_list: List[str]
    ):
        return (
            await FormDocument.find({"form_id": {"$in": form_id_list}})
            .aggregate(
                [
                    {
                        "$lookup": {
                            "from": "workspace_forms",
                            "localField": "form_id",
                            "foreignField": "form_id",
                            "as": "workspace_form",
                        }
                    },
                    {"$unwind": "$workspace_form"},
                    {"$match": {"workspace_form.workspace_id": workspace_id}},
                    {"$set": {"settings": "$workspace_form.settings"}},
                ]
            )
            .to_list()
        )
