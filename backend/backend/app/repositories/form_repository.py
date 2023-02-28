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
                            "from": "workspace_forms",
                            "localField": "formId",
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

    async def search_form_in_workspace(self, workspace_id: PydanticObjectId, form_ids: List[str], query: str):
        return await FormDocument.find(
            {
                "formId": {"$in": form_ids},
                "$or": [{"title": {"$regex": query, "$options": "i"}},
                        {"description": {"$regex": query, "$options": "i"}}],

            }
        ) \
            .aggregate(
            [
                {
                    "$lookup": {
                        "from": "workspace_forms",
                        "localField": "formId",
                        "foreignField": "form_id",
                        "as": "workspace_form",
                    }
                },
                {"$unwind": "$workspace_form"},
                {"$match": {"workspace_form.workspace_id": workspace_id}},
                {"$set": {"settings": "$workspace_form.settings"}},
            ]
        ).to_list()

    async def save_form(self, form: FormDocument):
        return await form.save()
