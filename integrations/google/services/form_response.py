from typing import Any, Dict, Optional

from common.enums.form_provider import FormProvider
from repositories.form_response import FormResponseRepository
from schemas.google_form_response import GoogleFormResponseDocument


class FormResponseService:
    def __init__(self, form_response_repo: FormResponseRepository):
        """
        Initializes the FormResponseService with a FormResponseRepository object.

        Args:
            form_response_repo: FormResponseRepository object
        """
        self.form_response_repo: FormResponseRepository = form_response_repo

    async def get_all_submissions(self):
        """
        Retrieve all google form submissions.

        Returns:
            A list of google form submissions.
        """
        return await self.form_response_repo.list()

    async def get_form_specific_submissions(self, form_id: str):
        """
        Retrieve all form specific google form submissions.

        Args:
            form_id (str): Form ID to retrieve form specific submissions.

        Returns:
            A list of form specific google form submissions.
        """
        return await self.form_response_repo.list_form_responses(form_id)

    async def get_submission(
        self, response_id: str, provider: FormProvider = FormProvider.GOOGLE
    ):
        """
        Retrieve a form submission by its ID and provider.

        Args:
            response_id: The ID of the form submissions to retrieve.
            provider: The provider of the form (default is Google).

        Returns:
            The form submission with the given ID and provider.
        """
        return await self.form_response_repo.get(response_id, provider)

    async def update_submission(
        self,
        form_id: str,
        response_id: str,
        form_response: Dict[str, Any],
        data_owner_field: Optional[str] = None,
    ):
        """
        Update a form submission by its ID and provider.

        Args:
            form_id: Form ID associated with the form response.
            response_id: The ID of the form response to update.
            form_response: The updated form response data.
            data_owner_field: Question id indicating the owner from its answer.
                e.g., What is your email address? -> A question with let's say an id "3e555b2b"
                      Responder responding to the form fills up this answer in the field, is set as owner.

        Returns: The updated form response.
        """
        response_document = GoogleFormResponseDocument(**form_response)
        response_document.formId = form_id
        response_document.provider = FormProvider.GOOGLE

        document = await self.get_submission(response_id)
        if document:
            response_document.dataOwnerFields = document.dataOwnerFields

        if response_document.respondentEmail:
            response_document.dataOwnerFields.append(
                {"respondentEmail": response_document.respondentEmail}
            )

        if response_document.answers and data_owner_field:
            answers = (
                response_document.answers.get(data_owner_field, {})
                .get("textAnswers", {})
                .get("answers", [])
            )
            if answers and type(answers) is list and len(answers) > 0:
                data_owner_pairs = {
                    data_owner_field: answers[0].get("value", {})
                    if answers[0].get("value")
                    else ""
                }
            else:
                data_owner_pairs = {data_owner_field: ""}
            response_document.dataOwnerFields.append(data_owner_pairs)

        # Check for duplication in dataOwnerFields
        unique_data_owner = list(
            set(tuple(d.items()) for d in response_document.dataOwnerFields)
        )
        response_document.dataOwnerFields = [dict(i) for i in unique_data_owner]
        return await self.form_response_repo.update(response_id, response_document)

    async def delete_submission(
        self, response_id: str, provider: FormProvider = FormProvider.GOOGLE
    ):
        """
        Deletes a form submission by its ID.

        Args:
            response_id: The ID of the form response to update.
            provider: The provider of the form (default is Google).

        Returns: The updated form response.
        """
        return await self.form_response_repo.delete(response_id, provider)
