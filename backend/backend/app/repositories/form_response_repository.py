import json
from typing import Any, Dict, List

import fastapi_pagination.ext.beanie
from beanie import PydanticObjectId
from fastapi_pagination import Page

from backend.app.models.filter_queries.form_responses import FormResponseFilterQuery
from backend.app.models.filter_queries.sort import SortRequest
from backend.app.models.response_dtos import StandardFormResponseCamelModel
from backend.app.repositories.deletion_requests_repository import (
    DeletionRequestsRepository,
)
from backend.app.schemas.standard_form_response import (
    FormResponseDocument,
    FormResponseDeletionRequest,
    DeletionRequestStatus,
)
from backend.app.utils.aggregation_query_builder import create_filter_pipeline
from common.base.repo import BaseRepository
from common.enums.form_provider import FormProvider
from common.models.standard_form import StandardFormResponse, StandardFormResponseAnswer
from common.models.user import User
from common.services.crypto_service import crypto_service


class FormResponseRepository(BaseRepository):
    @staticmethod
    async def get_form_responses(
        form_ids,
        extra_find_query: Dict[str, Any] = None,
        filter_query: FormResponseFilterQuery = None,
        sort: SortRequest = None,
    ) -> Page[StandardFormResponseCamelModel]:
        find_query = {"form_id": {"$in": form_ids}, "answers": {"$exists": True}}
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

        aggregate_query.extend(
            create_filter_pipeline(filter_object=filter_query, sort=sort)
        )

        form_responses_query = FormResponseDocument.find(find_query).aggregate(
            aggregate_query,
        )
        return await fastapi_pagination.ext.beanie.paginate(form_responses_query)

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
            return await self.get_workspace_responders(
                form_ids=form_ids, filter_query=filter_query, sort=sort
            )
        elif request_for_deletion:
            return await DeletionRequestsRepository.get_deletion_requests(
                form_ids,
                filter_query=filter_query,
                sort=sort,
            )
        else:
            return await self.get_form_responses(
                form_ids,
                filter_query=filter_query,
                sort=sort,
            )

    async def get_user_submissions(
        self, form_ids, user: User, request_for_deletion: bool = False
    ):
        extra_find_query = {
            "dataOwnerIdentifier": user.sub,
        }
        if request_for_deletion:
            return await DeletionRequestsRepository.get_deletion_requests(
                form_ids=form_ids, extra_find_query=extra_find_query
            )
        else:
            return await self.get_form_responses(form_ids, extra_find_query)

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
        self, form_id: PydanticObjectId, response: StandardFormResponse, workspace_id: PydanticObjectId
    ):
        response_document = FormResponseDocument(**response.dict())
        response_document.response_id = str(PydanticObjectId())
        if workspace_id and type(
            response_document.answers == StandardFormResponseAnswer
        ):
            for k, v in response_document.answers.items():
                response_document.answers[k] = v.dict()
            response_document.answers = crypto_service.encrypt(
                workspace_id=workspace_id,
                form_id=form_id,
                data=json.dumps(response_document.answers),
            )
        response_document.form_id = str(form_id)
        response_document.provider = "self"
        return await response_document.save()

    async def delete_form_response(
        self, form_id: PydanticObjectId, response_id: PydanticObjectId
    ):
        await FormResponseDocument.find(
            {"form_id": str(form_id), "response_id": str(response_id)}
        ).delete()
        await FormResponseDeletionRequest.find(
            {"form_id": str(form_id), "response_id": str(response_id)}
        ).update(
            {
                "$set": {"status": DeletionRequestStatus.SUCCESS},
            }
        )
        return str(response_id)
