import json
from typing import Any, Dict

from beanie import PydanticObjectId

from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.models.workspace import WorkspaceResponseDto
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.schemas.standard_form_response import (
    DeletionRequestStatus,
    FormResponseDeletionRequest,
    FormResponseDocument,
)
from backend.app.services.form_service import FormService
from common.models.form_import import FormImportResponse
from common.models.standard_form import StandardForm, StandardFormResponseAnswer
from common.services.crypto_service import crypto_service


class FormImportService:
    def __init__(
        self,
        form_service: FormService,
        workspace_repo: WorkspaceRepository,
    ):
        self.form_service = form_service
        self._workspace_repo = workspace_repo

    async def get_form_workspace_by_id(self, workspace_id: PydanticObjectId):
        return await self._workspace_repo.get_workspace_by_id(workspace_id=workspace_id)

    async def save_converted_form_and_responses(
        self,
        response_data: Dict[str, Any],
        form_response_data_owner: str,
        workspace_id: PydanticObjectId,
    ) -> StandardForm | None:
        form_data = FormImportResponse.parse_obj(response_data)
        if not (form_data.form or form_data.responses):
            return None
        standard_form = form_data.form
        await self.form_service.save_form(standard_form)
        responses = form_data.responses

        updated_responses_id = []

        for response in responses:
            existing_response = await FormResponseDocument.find_one(
                {"response_id": response.response_id}
            )
            response_document = FormResponseDocument(**response.dict())
            if existing_response:
                response_document.id = existing_response.id
            response_document.form_id = standard_form.form_id
            data_owner_answer = response_document.answers.get(form_response_data_owner)

            if not response_document.dataOwnerIdentifier:
                response_document.dataOwnerIdentifier = (
                    data_owner_answer.text
                    or data_owner_answer.email
                    or data_owner_answer.phone_number
                    or data_owner_answer.number
                    if data_owner_answer
                    else None
                )
            if workspace_id and type(
                response_document.answers == StandardFormResponseAnswer
            ):
                for k, v in response_document.answers.items():
                    response_document.answers[k] = v.dict()
                response_document.answers = crypto_service.encrypt(
                    workspace_id=workspace_id,
                    form_id=response_document.form_id,
                    data=json.dumps(response_document.answers),
                )
            await response_document.save()
            updated_responses_id.append(response.response_id)

        deletion_requests_query = {
            "form_id": standard_form.form_id,
            "provider": standard_form.settings.provider,
            "response_id": {"$nin": updated_responses_id},
        }

        await FormResponseDocument.find(
            {
                "form_id": standard_form.form_id,
                "response_id": {"$nin": updated_responses_id},
            }
        ).delete()

        updated_result = await FormResponseDeletionRequest.find(
            deletion_requests_query
        ).update_many(
            {
                "$set": {"status": DeletionRequestStatus.SUCCESS},
            }
        )
        if updated_result.modified_count >= 1:
            workspace = await self._workspace_repo.get_workspace_by_id(
                workspace_id=workspace_id
            )
            await self.form_service.user_tags_service.add_user_tag(
                user_id=WorkspaceResponseDto(**workspace.dict()).owner_id,
                tag=UserTagType.DELETION_REQUEST_PROCESSED,
            )
        return standard_form

