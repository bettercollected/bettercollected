from http import HTTPStatus
from typing import List

from pymongo.errors import (
    InvalidOperation,
    InvalidURI,
    NetworkTimeout,
    OperationFailure,
)

from backend.app.exceptions import HTTPException
from backend.app.schemas.standard_form_response import FormResponseDocument
from common.base.repo import BaseRepository, T, U
from common.constants import MESSAGE_DATABASE_EXCEPTION, MESSAGE_NOT_FOUND
from common.enums.form_provider import FormProvider
from common.models.standard_form import StandardFormResponseDto
from common.models.user import User


# noinspection PyMethodOverriding
class FormResponseRepository(BaseRepository):
    async def list(self, form_id: str) -> List[StandardFormResponseDto]:
        try:
            form_responses = (
                await FormResponseDocument.find({"form_id": form_id})
                .aggregate(
                    [
                        {
                            "$lookup": {
                                "from": "forms",
                                "localField": "form_id",
                                "foreignField": "form_id",
                                "as": "form",
                            },
                        },
                        {"$set": {"title": "$form.title"}},
                        {"$unwind": "$title"},
                        {"$sort": {"created_at": -1}},
                    ]
                )
                .to_list()
            )
            return [
                StandardFormResponseDto(**form_response)
                for form_response in form_responses
            ]
        # TODO : Handle specific exception on global exception handler
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content=MESSAGE_DATABASE_EXCEPTION,
            )

    async def list_by_form_ids(
        self, form_ids: List[str]
    ) -> List[StandardFormResponseDto]:
        try:
            form_responses = (
                await FormResponseDocument.find({"form_id": {"$in": form_ids}})
                .aggregate(
                    [
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
                        {"$sort": {"created_at": -1}},
                    ]
                )
                .to_list()
            )
            return [
                StandardFormResponseDto(**form_response)
                for form_response in form_responses
            ]
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content=MESSAGE_DATABASE_EXCEPTION,
            )

    async def get_user_submissions(self, form_ids, user: User):
        try:
            form_responses = (
                await FormResponseDocument.find(
                    {"dataOwnerIdentifier": user.sub, "form_id": {"$in": form_ids}}
                )
                .aggregate(
                    [
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
                        {"$sort": {"created_at": -1}},
                    ]
                )
                .to_list()
            )
            return [
                StandardFormResponseDto(**form_response)
                for form_response in form_responses
            ]

        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content=MESSAGE_DATABASE_EXCEPTION,
            )

    async def get(self, form_id: str, response_id: str) -> StandardFormResponseDto:
        try:
            document = (
                await FormResponseDocument.find(
                    {"form_id": form_id, "response_id": response_id}
                )
                .aggregate(
                    [
                        {
                            "$lookup": {
                                "from": "forms",
                                "localField": "form_id",
                                "foreignField": "form_id",
                                "as": "form",
                            },
                        },
                        {
                            "$set": {
                                "title": "$form.title",
                                "provider": "$form.provider",
                            }
                        },
                        {"$unwind": "$title"},
                        {"$unwind": "$provider"},
                        {
                            "$lookup": {
                                "from": "workspace_forms",
                                "localField": "form_id",
                                "foreignField": "form_id",
                                "as": "workspace_form",
                            }
                        },
                        {
                            "$set": {
                                "formCustomUrl": "$workspace_form.settings.custom_url"
                            }
                        },
                        {"$unwind": "$formCustomUrl"},
                    ]
                )
                .to_list()
            )
            if not document:
                raise HTTPException(
                    status_code=HTTPStatus.NOT_FOUND,
                    content=MESSAGE_NOT_FOUND,
                )
            if document and len(document) > 1:
                raise HTTPException(
                    status_code=HTTPStatus.CONFLICT,
                    content="Found multiple form response document with the provided response id.",
                )
            return StandardFormResponseDto(**document[0].dict())
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content=MESSAGE_DATABASE_EXCEPTION,
            )

    async def add(self, item: FormResponseDocument) -> StandardFormResponseDto:
        pass

    async def update(
        self, item_id: str, item: FormResponseDocument
    ) -> StandardFormResponseDto:
        pass

    async def delete(self, item_id: str, provider: FormProvider):
        pass
