from typing import List

from beanie import PydanticObjectId
from beanie.odm.queries.aggregation import AggregationQuery

from backend.app.exceptions import HTTPException
from backend.app.schemas.standard_form import FormDocument
from backend.app.utils.aggregation_query_builder import create_filter_pipeline
from common.models.standard_form import StandardForm


class FormRepository:
    @staticmethod
    def get_forms_in_workspace_query(
        workspace_id: PydanticObjectId,
        form_id_list: List[str],
        is_admin: bool,
        sort=None,
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
            {
                "$set": {
                    "settings": "$workspace_form.settings",
                    "imported_by": "$workspace_form.user_id",
                }
            },
            {
                "$lookup": {
                    "from": "responder_group_form",
                    "localField": "form_id",
                    "foreignField": "form_id",
                    "as": "form_groups",
                }
            },
            {
                "$lookup": {
                    "from": "responder_group",
                    "localField": "form_groups.group_id",
                    "foreignField": "_id",
                    "as": "groups",
                }
            },
        ]

        aggregation_pipeline.extend(create_filter_pipeline(sort=sort))

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
                    {
                        "$set": {
                            "responses": {
                                "$filter": {
                                    "input": "$responses",
                                    "as": "item",
                                    "cond": {
                                        "$ne": [{"$type": "$$item.answers"}, "missing"]
                                    },
                                }
                            }
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
                    {
                        "$set": {
                            "settings": "$workspace_form.settings",
                            "imported_by": "$workspace_form.user_id",
                        }
                    },
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

    async def delete_forms(self, form_ids: List[str]):
        return await FormDocument.find({"form_id": {"$in": form_ids}}).delete()

    async def create_form(self, form: StandardForm) -> FormDocument:
        form_document = FormDocument(**form.dict())
        return await form_document.save()

    async def update_form(self, form_id: PydanticObjectId, form: StandardForm):
        form_document = await FormDocument.find_one({"form_id": str(form_id)})
        form_document.fields = form.fields
        form_document.title = form.title
        form_document.logo = form.logo
        form_document.cover_image = form.cover_image
        form_document.description = form.description
        form_document.button_text = form.button_text
        form_document.consent = form.consent
        return await form_document.save()
