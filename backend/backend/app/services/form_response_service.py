import json
from http import HTTPStatus
from typing import List, Sequence

from beanie import PydanticObjectId
from fastapi_pagination import Page

from backend.app.exceptions import HTTPException
from backend.app.models.filter_queries.form_responses import FormResponseFilterQuery
from backend.app.models.filter_queries.sort import SortRequest
from backend.app.models.response_dtos import (
    StandardFormCamelModel,
    StandardFormResponseCamelModel,
)
from backend.app.repositories.form_response_repository import FormResponseRepository
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.standard_form_response import (
    FormResponseDeletionRequest,
    FormResponseDocument,
)
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from common.constants import MESSAGE_UNAUTHORIZED
from common.models.standard_form import StandardFormResponse
from common.models.user import User
from common.services.crypto_service import crypto_service


class FormResponseService:
    def __init__(
        self,
        form_response_repo: FormResponseRepository,
        workspace_form_repo: WorkspaceFormRepository,
        workspace_user_repo: WorkspaceUserRepository,
    ):
        self._form_response_repo = form_response_repo
        self._workspace_form_repo = workspace_form_repo
        self._workspace_user_repo = workspace_user_repo

    async def get_all_workspace_responses(
        self,
        workspace_id: PydanticObjectId,
        filter_query: FormResponseFilterQuery,
        sort: SortRequest,
        request_for_deletion: bool,
        user: User,
        data_subjects: bool = None,
    ):
        if not await self._workspace_user_repo.has_user_access_in_workspace(
            workspace_id=workspace_id, user=user
        ):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, content=MESSAGE_UNAUTHORIZED
            )
        form_ids = await self._workspace_form_repo.get_form_ids_in_workspace(
            workspace_id=workspace_id
        )
        responses_page = await self._form_response_repo.list(
            form_ids,
            request_for_deletion,
            data_subjects=data_subjects,
            filter_query=filter_query,
            sort=sort,
        )
        if not (data_subjects or request_for_deletion):
            return self.decrypt_response_page(
                workspace_id=workspace_id, responses_page=responses_page
            )
        return responses_page

    async def get_user_submissions(
        self,
        workspace_id: PydanticObjectId,
        user: User,
        request_for_deletion: bool = False,
    ):
        form_ids = await self._workspace_form_repo.get_form_ids_in_workspace(
            workspace_id
        )
        user_responses = await self._form_response_repo.get_user_submissions(
            form_ids=form_ids, user=user, request_for_deletion=request_for_deletion
        )
        if not request_for_deletion:
            return self.decrypt_response_page(
                workspace_id=workspace_id, responses_page=user_responses
            )
        return user_responses

    async def get_workspace_form_submissions(
        self,
        workspace_id: PydanticObjectId,
        request_for_deletion: bool,
        form_id: str,
        filter_query: FormResponseFilterQuery,
        sort: SortRequest,
        user: User,
    ):
        if not await self._workspace_user_repo.has_user_access_in_workspace(
            workspace_id, user
        ):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, content=MESSAGE_UNAUTHORIZED
            )
        workspace_form = (
            await self._workspace_form_repo.get_workspace_form_in_workspace(
                workspace_id, form_id
            )
        )
        if not workspace_form:
            raise HTTPException(
                HTTPStatus.NOT_FOUND, "Form not found in the workspace."
            )
        form_responses = await self._form_response_repo.list(
            [form_id], request_for_deletion, filter_query, sort
        )

        if not request_for_deletion:
            return self.decrypt_response_page(
                workspace_id=workspace_id, responses_page=form_responses
            )
        return form_responses

    async def get_workspace_submission(
        self, workspace_id: PydanticObjectId, response_id: str, user: User
    ):
        is_admin = await self._workspace_user_repo.has_user_access_in_workspace(
            workspace_id, user
        )
        # TODO : Handle case for multiple form import by other user
        # TODO : Combine all queries to one
        response = await FormResponseDocument.find_one({"response_id": response_id})
        form = await FormDocument.find_one({"form_id": response.form_id})
        deletion_request = await FormResponseDeletionRequest.find_one(
            {"response_id": response_id}
        )
        workspace_form = await WorkspaceFormDocument.find_one(
            {
                "workspace_id": workspace_id,
                "form_id": form.form_id,
            }
        )
        if not workspace_form:
            raise HTTPException(404, "Form not found in this workspace")

        if not (is_admin or response.dataOwnerIdentifier == user.sub):
            raise HTTPException(403, "You are not authorized to perform this action.")

        response = StandardFormResponseCamelModel(**response.dict())
        if deletion_request is not None:
            response.deletion_status = deletion_request.status
        form = StandardFormCamelModel(**form.dict())
        form.settings = workspace_form.settings
        response.form_title = form.title
        return {
            "form": form,
            "response": self.decrypt_form_response(
                workspace_id=workspace_id, response=response
            ),
        }

    async def request_for_response_deletion(
        self, workspace_id: PydanticObjectId, response_id: str, user: User
    ):
        is_admin = await self._workspace_user_repo.has_user_access_in_workspace(
            workspace_id, user
        )
        # TODO : Handle case for multiple form import by other user
        response = await FormResponseDocument.find_one({"response_id": response_id})

        if not (is_admin or response.dataOwnerIdentifier == user.sub):
            raise HTTPException(403, "You are not authorized to perform this action.")

        deletion_request = await FormResponseDeletionRequest.find_one(
            {"response_id": response_id}
        )
        if deletion_request:
            raise HTTPException(
                400,
                "Error: Deletion request already exists for the response : "
                + response_id,
            )

        await FormResponseDeletionRequest(
            form_id=response.form_id,
            response_id=response_id,
            dataOwnerIdentifier=response.dataOwnerIdentifier,
            provider=response.provider,
        ).save()

    async def get_responses_count_in_workspace(self, workspace_form_ids: List[str]):
        return await self._form_response_repo.count_responses_for_form_ids(
            workspace_form_ids
        )

    async def get_deletion_requests_count_in_workspace(self, form_ids: List[str]):
        return await self._form_response_repo.get_deletion_requests_count_in_workspace(
            form_ids
        )

    async def delete_form_responses(self, form_id):
        return await self._form_response_repo.delete_by_form_id(form_id)

    async def delete_deletion_requests(self, form_id):
        return await self._form_response_repo.delete_deletion_requests(form_id=form_id)

    async def delete_form_responses_of_form_ids(self, form_ids):
        return await self._form_response_repo.delete_by_form_ids(form_ids=form_ids)

    async def delete_deletion_requests_of_form_ids(self, form_ids):
        return await self._form_response_repo.delete_deletion_requests_by_form_ids(
            form_ids=form_ids
        )

    def decrypt_response_page(
        self,
        workspace_id: PydanticObjectId,
        responses_page: Page[StandardFormResponseCamelModel],
    ):
        responses_page.items = self.decrypt_form_responses(
            workspace_id=workspace_id, responses=responses_page.items
        )
        return responses_page

    def decrypt_form_responses(
        self,
        workspace_id: PydanticObjectId,
        responses: Sequence[StandardFormResponseCamelModel],
    ):
        for response in responses:
            response = self.decrypt_form_response(
                workspace_id=workspace_id, response=response
            )
        return responses

    def decrypt_form_response(
        self, workspace_id: PydanticObjectId, response: StandardFormResponseCamelModel
    ):
        if isinstance(response.answers, dict):
            return response
        response.answers = json.loads(
            crypto_service.decrypt(
                workspace_id=workspace_id,
                form_id=response.form_id,
                data=response.answers,
            )
        )
        return response

    async def submit_form_response(
        self, form_id: PydanticObjectId, response: StandardFormResponse
    ):
        return await self._form_response_repo.save_form_response(
            form_id=form_id, response=response
        )

    async def delete_form_response(
        self, form_id: PydanticObjectId, response_id: PydanticObjectId
    ):
        return await self._form_response_repo.delete_form_response(
            form_id=form_id, response_id=response_id
        )
