from typing import Any, Dict, List

from backend.app.schemas.standard_form_response import FormResponseDocument

from common.base.repo import BaseRepository
from common.enums.form_provider import FormProvider
from common.models.standard_form import StandardFormResponse
from common.models.user import User

import fastapi_pagination.ext.beanie
from fastapi_pagination import Page


class FormResponseRepository(BaseRepository):
    @staticmethod
    async def get_form_responses(
        form_ids,
        request_for_deletion: bool,
        extra_find_query: Dict[str, Any] = None,
    ) -> Page[FormResponseDocument]:
        find_query = {"form_id": {"$in": form_ids}}
        if not request_for_deletion:
            find_query["answers"] = {"$exists": True}
        if extra_find_query:
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
        aggregate_query.append({"$sort": {"created_at": -1}})
        form_responses_query = FormResponseDocument.find(find_query).aggregate(
            aggregate_query
        )
        form_responses = await fastapi_pagination.ext.beanie.paginate(
            form_responses_query
        )
        return form_responses

    async def list(
        self, form_ids: List[str], request_for_deletion: bool
    ) -> Page[StandardFormResponse]:
        form_responses = await self.get_form_responses(form_ids, request_for_deletion)
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

    async def count_responses_for_form_ids(self, form_ids) -> int:
        return await FormResponseDocument.find({"form_id": {"$in": form_ids}}).count()

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
