from typing import Any, Dict, List, Sequence

import fastapi_pagination.ext.beanie
from beanie import PydanticObjectId
from fastapi_pagination import Page

from backend.app.models.filter_queries.form_responses import FormResponseFilterQuery
from backend.app.models.filter_queries.sort import SortRequest
from backend.app.models.response_dtos import StandardFormResponseCamelModel
from backend.app.schemas.standard_form_response import (
    FormResponseDocument,
    FormResponseDeletionRequest,
    DeletionRequestStatus,
)
from backend.app.utils.aggregation_query_builder import create_filter_pipeline
from common.base.repo import BaseRepository
from common.enums.form_provider import FormProvider
from common.models.standard_form import StandardFormResponse
from common.models.user import User


class FormResponseRepository(BaseRepository):
    @staticmethod
    async def get_form_responses(
        form_ids,
        request_for_deletion: bool,
        extra_find_query: Dict[str, Any] = None,
        filter_query: FormResponseFilterQuery = None,
        sort: SortRequest = None,
    ) -> Page[FormResponseDocument]:
        find_query = {"form_id": {"$in": form_ids}}
        if not request_for_deletion:
            find_query["answers"] = {"$exists": True}
        if extra_find_query is not None:
            find_query.update(extra_find_query)
        aggregate_query = [
            {
                "$lookup": {
                    "from": "forms",
                    "localField": "form_id",
                    "foreignField": "form_id",
                    "as": "form",
                },
            },
            {"$set": {"form_title": "$form.title"}},
            {"$unwind": "$form_title"},
        ]

        if request_for_deletion:
            aggregate_query.extend(
                [
                    {
                        "$lookup": {
                            "from": "responses_deletion_requests",
                            "localField": "response_id",
                            "foreignField": "response_id",
                            "as": "deletion_request",
                        }
                    },
                    {"$unwind": "$deletion_request"},
                    {
                        "$set": {
                            "deletion_status": "$deletion_request.status",
                            "updated_at": "$deletion_request.created_at",
                            "created_at": "$deletion_request.created_at",
                        }
                    },
                ]
            )

        aggregate_query.extend(
            create_filter_pipeline(filter_object=filter_query, sort=sort)
        )

        def transformer(items: Sequence[Any]):
            for item in items:
                item["answers"] = None
            return items

        deletion_transformer = transformer if request_for_deletion else None

        form_responses_query = FormResponseDocument.find(find_query).aggregate(
            aggregate_query,
        )
        form_responses = await fastapi_pagination.ext.beanie.paginate(
            form_responses_query, transformer=deletion_transformer
        )
        return form_responses

    async def get_workspace_responders(
        self,
        form_ids: List[str],
        filter_query: FormResponseFilterQuery = None,
        sort: SortRequest = None,
    ):
        find_query = {"form_id": {"$in": form_ids}}

        aggregate_query = [
            {"$match": {"dataOwnerIdentifier": {"$exists": True, "$ne": None}}},
            {
                "$group": {
                    "_id": "$dataOwnerIdentifier",
                    "response_ids": {"$push": "$$CURRENT.response_id"},
                    "responses": {"$sum": 1},
                }
            },
            {
                "$lookup": {
                    "from": "responses_deletion_requests",
                    "localField": "response_ids",
                    "foreignField": "response_id",
                    "as": "deletion_requests",
                }
            },
            {
                "$project": {
                    "email": "$_id",
                    "_id": 0,
                    "responses": 1,
                    "deletion_requests": {"$size": "$deletion_requests"},
                }
            },
            {
                "$lookup": {
                    "from": "workspace_responder",
                    "localField": "email",
                    "foreignField": "email",
                    "as": "responder",
                }
            },
            {
                "$unwind": {
                    "path": "$responder",
                    "preserveNullAndEmptyArrays": True,
                }
            },
            {
                "$set": {
                    "tags": "$responder.tags",
                    "metadata": "$responder.metadata",
                }
            },
            {
                "$lookup": {
                    "from": "workspace_tags",
                    "localField": "tags",
                    "foreignField": "_id",
                    "as": "tags",
                }
            },
            {"$sort": {"email": 1}},
        ]

        aggregate_query.extend(
            create_filter_pipeline(
                filter_object=filter_query, sort=sort, default_sort=False
            )
        )

        form_responses_query = FormResponseDocument.find(find_query).aggregate(
            aggregate_query
        )
        form_responses = await fastapi_pagination.ext.beanie.paginate(
            form_responses_query
        )
        return form_responses

    async def list(
        self,
        form_ids: List[str],
        request_for_deletion: bool,
        filter_query: FormResponseFilterQuery = None,
        sort: SortRequest = None,
        data_subjects: bool = None,
    ) -> Page[StandardFormResponseCamelModel]:
        if data_subjects:
            form_responses = await self.get_workspace_responders(
                form_ids=form_ids, filter_query=filter_query, sort=sort
            )

        else:
            form_responses = await self.get_form_responses(
                form_ids,
                request_for_deletion,
                filter_query=filter_query,
                sort=sort,
            )
        return form_responses

    async def get_user_submissions(
        self, form_ids, user: User, request_for_deletion: bool = False
    ):
        extra_find_query = {
            "dataOwnerIdentifier": user.sub,
        }
        form_responses = await self.get_form_responses(
            form_ids, request_for_deletion, extra_find_query
        )
        return form_responses

    async def count_responses_for_form_ids(self, form_ids: List[str]) -> int:
        return await FormResponseDocument.find({"form_id": {"$in": form_ids}}).count()

    async def get_deletion_requests_count_in_workspace(self, form_ids: List[str]):
        success_deletion_request = (
            await FormResponseDeletionRequest.find({"form_id": {"$in": form_ids}})
            .aggregate(
                [
                    {
                        "$facet": {
                            "success": [
                                {"$match": {"status": DeletionRequestStatus.SUCCESS}},
                                {"$count": "total"},
                            ],
                            "pending": [
                                {"$match": {"status": DeletionRequestStatus.PENDING}},
                                {"$count": "total"},
                            ],
                            "total": [{"$count": "total"}],
                        }
                    },
                    {
                        "$addFields": {
                            "success": {"$arrayElemAt": ["$success.total", 0]},
                            "pending": {"$arrayElemAt": ["$pending.total", 0]},
                            "total": {"$arrayElemAt": ["$total.total", 0]},
                        }
                    },
                ]
            )
            .to_list()
        )
        return success_deletion_request[0]

    async def get(self, form_id: str, response_id: str) -> StandardFormResponse:
        pass

    async def add(self, item: FormResponseDocument) -> StandardFormResponse:
        pass

    async def update(
        self, item_id: str, item: FormResponseDocument
    ) -> StandardFormResponse:
        pass

    async def delete(self, item_id: str, provider: FormProvider):
        pass

    async def delete_by_form_id(self, form_id):
        return await FormResponseDocument.find({"form_id": form_id}).delete()

    async def delete_deletion_requests(self, form_id: str):
        return await FormResponseDeletionRequest.find({"form_id": form_id}).delete()

    async def delete_by_form_ids(self, form_ids):
        return await FormResponseDocument.find({"form_id": {"$in": form_ids}}).delete()

    async def delete_deletion_requests_by_form_ids(self, form_ids):
        return await FormResponseDeletionRequest.find(
            {"form_id": {"$in": form_ids}}
        ).delete()

    async def save_form_response(
        self, form_id: PydanticObjectId, response: StandardFormResponse
    ):
        response_document = FormResponseDocument(**response.dict())
        response_document.response_id = str(PydanticObjectId())
        response_document.form_id = str(form_id)
        return await response_document.save()
