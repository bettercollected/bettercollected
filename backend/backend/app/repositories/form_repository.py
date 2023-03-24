from typing import List

from backend.app.schemas.standard_form import FormDocument

from beanie import PydanticObjectId
from beanie.odm.queries.aggregation import AggregationQuery


class FormRepository:
    @staticmethod
    def get_forms_in_workspace_query(
        workspace_id: PydanticObjectId, form_id_list: List[str]
    ) -> AggregationQuery:
        forms = FormDocument.find({"form_id": {"$in": form_id_list}}).aggregate(
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
        return forms

    async def search_form_in_workspace(
        self, workspace_id: PydanticObjectId, form_ids: List[str], query: str
    ):
        return (
            await FormDocument.find(
                {
                    "form_id": {"$in": form_ids},
                    "$or": [
                        {"title": {"$regex": query, "$options": "i"}},
                        {"description": {"$regex": query, "$options": "i"}},
                    ],
                }
            )
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

    async def save_form(self, form: FormDocument):
        return await form.save()
