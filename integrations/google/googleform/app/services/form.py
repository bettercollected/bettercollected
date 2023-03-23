from typing import Any, Dict, Optional

from common.enums.form_provider import FormProvider

from googleform.app.repositories.form import FormRepository
from googleform.app.schemas.google_form import GoogleFormDocument
from googleform.app.schemas.oauth_credential import Oauth2CredentialDocument


class FormService:
    def __init__(self, form_repo: FormRepository):
        """
        Initializes the FormService with a FormRepository object.

        Args:
            form_repo: FormRepository object
        """
        self.form_repo: FormRepository = form_repo

    async def convert_form(
        self,
        form_import: Dict[str, Any],
        convert_responses: bool,
        credential: Oauth2CredentialDocument,
    ):
        # transformer =
        pass

    async def get_forms(self):
        """
        Retrieve all forms.

        Returns:
            A list of forms.
        """
        return await self.form_repo.list()

    async def get_form(
        self, form_id: str, provider: FormProvider = FormProvider.GOOGLE
    ):
        """
        Retrieve a form by its ID and provider.

        Args:
            form_id: The ID of the form to retrieve.
            provider: The provider of the form (default is Google).

        Returns:
            The form with the given ID and provider.
        """
        return await self.form_repo.get(form_id, provider)

    async def update_form(
        self, form_id: str, form: Dict[str, Any], data_owner_field: Optional[str] = None
    ):
        """
        Update a form by its ID and provider.

        Args:
            form_id: The ID of the form to update.
            form: The updated form data.
            data_owner_field: Question id indicating the owner from its answer.
                e.g., What is your email address? -> A question with let's say
                an id "3e555b2b", Responder responding to the form fills up
                this answer in the field, is set as owner.

        Returns: The updated form.
        """
        form_document = GoogleFormDocument(**form)
        form_document.provider = FormProvider.GOOGLE
        document = await self.get_form(form_id)
        if document:
            form_document.dataOwnerFields = list(
                set(
                    document.dataOwnerFields + [data_owner_field]
                    if data_owner_field
                    else document.dataOwnerFields
                )
            )  # Removing duplicate question id as data owner fields
        elif data_owner_field:
            form_document.dataOwnerFields.append(data_owner_field)
        return await self.form_repo.update(form_id, form_document)
