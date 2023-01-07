from common.enums.form_provider import FormProvider
from common.schemas.google_form import GoogleFormDocument
from repositories.form import FormRepository


class FormService:
    def __init__(self, form_repo: FormRepository):
        """
        Initializes the FormService with a FormRepository object.

        Args:
            form_repo: FormRepository object
        """
        self.form_repo: FormRepository = form_repo

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

    async def update_form(self, form_id: str, form: GoogleFormDocument):
        """
        Update a form by its ID and provider.

        Args:
            form_id: The ID of the form to update.
            form: The updated form data.

        Returns: The updated form.
        """
        return await self.form_repo.update(form_id, form)
