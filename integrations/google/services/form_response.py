from common.enums.form_provider import FormProvider
from common.schemas.google_form_response import GoogleFormResponseDocument
from repositories.form_response import FormResponseRepository


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

    async def add_submission(
        self, form_id: str, form_response: GoogleFormResponseDocument
    ):
        """
        Add a form submission by its ID and provider.

        Args:
            form_id: Form ID associated with the form response.
            form_response: The updated form response data.

        Returns: The updated form response.
        """
        # TODO: perform validation and fetch google form responses of form_id from GOOGLE API
        _ = form_id
        return await self.form_response_repo.add(form_response)

    async def update_submission(
        self, form_id: str, response_id: str, form_response: GoogleFormResponseDocument
    ):
        """
        Update a form submission by its ID and provider.

        Args:
            form_id: Form ID associated with the form response.
            response_id: The ID of the form response to update.
            form_response: The updated form response data.

        Returns: The updated form response.
        """
        # TODO: perform validation and fetch google form responses of form_id from GOOGLE API
        _ = form_id
        return await self.form_response_repo.update(response_id, form_response)

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
