from typing import Dict, Any

from backend.app.schemas.standard_form_response import FormResponseDocument
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
                data_owner_answer.text if data_owner_answer else None
            )
            response_document.request_for_deletion = existing_response.request_for_deletion
            await response_document.save()

        return standard_form
