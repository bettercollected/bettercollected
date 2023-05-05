from typing import List

from backend.app.exceptions import HTTPException
from backend.app.schemas.standard_form import FormDocument

from beanie import PydanticObjectId
from beanie.odm.queries.aggregation import AggregationQuery


class FormRepository:
    @staticmethod
    def get_forms_in_workspace_query(
        workspace_id: PydanticObjectId, form_id_list: List[str], is_admin: bool
    ) -> AggregationQuery:
        aggregation_pipeline = [
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
            {"$set": {"settings": "$workspace_form.settings", "imported_by": "$workspace_form.user_id"}},
        ]

        if is_admin:
            aggregation_pipeline.extend(
                [
                    {
                        "$lookup": {
                            "from": "form_responses",
                            "localField": "form_id",
                            "foreignField": "form_id",
                            "as": "responses",
                        }
                    },
                    {"$set": {"responses": {"$size": "$responses"}}},
                    {
                        "$lookup": {
                            "from": "responses_deletion_requests",
                            "localField": "form_id",
                            "foreignField": "form_id",
                            "as": "responses_deletion_requests",
                        }
                    },
                    {
                        "$set": {
                            "deletion_requests": {
                                "$size": "$responses_deletion_requests"
                            }
                        }
                    },
                ]
            )
        forms = FormDocument.find({"form_id": {"$in": form_id_list}}).aggregate(
            aggregation_pipeline
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
                    {"$set": {"settings": "$workspace_form.settings", "imported_by": "$workspace_form.user_id"}},
                ]
            )
            .to_list()
        )

    async def save_form(self, form: FormDocument):
        return await form.save()

    async def delete_form(self, form_id: str):
        form = await FormDocument.find_one({"form_id": form_id})
        if not form:
            raise HTTPException(status_code=404, content="Form not found")
        return await form.delete()
