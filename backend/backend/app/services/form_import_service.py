from typing import Dict, Any

from pydantic import BaseModel

from backend.app.schemas.standard_form_response import (
    FormResponseDocument,
    FormResponseDeletionRequest,
    DeletionRequestStatus,
)
from backend.app.services.form_service import FormService
from common.models.form_import import FormImportResponse
from common.models.standard_form import StandardForm


class FormImportService:
    def __init__(self, form_service: FormService):
        self.form_service = form_service

    async def save_converted_form_and_responses(
        self, response_data: Dict[str, Any], form_response_data_owner: str
    ) -> StandardForm:
        form_data = FormImportResponse.parse_obj(response_data)
        standard_form = form_data.form
        await self.form_service.save_form(standard_form)
        responses = form_data.responses

        updated_responses_id = []

        # TODO : Make this scalable in case of large number of responses
        for response in responses:
            existing_response = await FormResponseDocument.find_one(
                {"response_id": response.response_id}
            )
            response_document = FormResponseDocument(**response.dict())
            if existing_response:
                response_document.id = existing_response.id
            response_document.form_id = standard_form.form_id
            # TODO : Handle data owner identifier in workspace
            data_owner_answer = response_document.answers.get(form_response_data_owner)
            response_document.dataOwnerIdentifier = (
                data_owner_answer.text
                or data_owner_answer.email
                or data_owner_answer.phone_number
                or data_owner_answer.number
                if data_owner_answer
                else None
            )
            await response_document.save()
            updated_responses_id.append(response.response_id)

        deletion_requests_query = {
            "form_id": standard_form.form_id,
            "provider": standard_form.settings.provider,
            "response_id": {"$nin": updated_responses_id},
        }
        deletion_requests = await FormResponseDeletionRequest.find(
            deletion_requests_query
        ).to_list()

        if deletion_requests:
            await FormResponseDocument.find(
                {
                    "form_id": standard_form.form_id,
                    "response_id": {
                        "$in": [
                            deleted_response.response_id
                            for deleted_response in deletion_requests
                        ]
                    },
                }
            ).delete_many()

            await FormResponseDeletionRequest.find(deletion_requests_query).update_many(
                {"status": DeletionRequestStatus.SUCCESS}
            )

        return standard_form
