from datetime import datetime
from typing import List

from common.enums.form_provider import FormProvider
from common.models.form_scheduler_config import AddNewFormImportJobRequest
from common.schemas.form_scheduler_config import SchedulerFormConfigDocument
from repositories.form_scheduler_config import FormSchedulerConfigRepository


class FormSchedulerConfigService:
    """
    Class for interacting with the Form Scheduler Configurations.

    This class provides a convenient way to access the Form Scheduler
    Configurations and perform various operations on it.
    """

    def __init__(self, fsc_repo: FormSchedulerConfigRepository):
        """
        Initialize the FormSchedulerConfigRepository instance

        Args:
            fsc_repo: (FormSchedulerConfigRepository) instance of the
                FormSchedulerConfigRepository to perform CRUD operation
        """
        self.fsc_repo: FormSchedulerConfigRepository = fsc_repo

    async def get_all_form_scheduler_configs(self) -> List[SchedulerFormConfigDocument]:
        """
        Retrieve all Form Scheduler Configurations.

        Returns:
            list: A list of Form Scheduler Configurations documents.
        """
        return await self.fsc_repo.list()

    async def get_form_scheduler_config(
        self, form_id: str, provider: FormProvider
    ) -> SchedulerFormConfigDocument | None:
        """
        Retrieve a Form Scheduler Configuration for a given form id and provider.

        Args:
            form_id (str): Form ID
            provider (FormProvider): Provider of the form

        Returns:
            dict: Form Scheduler Configuration document.
        """
        return await self.fsc_repo.get(form_id, provider)

    async def add_new_form_import_job(
        self, client: AddNewFormImportJobRequest
    ) -> SchedulerFormConfigDocument | None:
        """
        Add a new Form Scheduler Configuration.

        Args:
            client (AddNewFormImportJobRequest): request object that contains
                formId, provider, email.

        Returns:
            SchedulerFormConfigDocument | None:  Document added or updated
        """
        document = await self.fsc_repo.get(
            form_id=client.formId, provider=client.provider
        )
        if document:
            document.email = (
                list({*document.email, *client.email})
                if document.email
                else [*client.email]
            )
            document.provider = client.provider
            document.formId = client.formId
            document.imported_at = datetime.now()
            document = await self.fsc_repo.update(client.formId, item=document)
            return document

        document = await self.fsc_repo.add(client)
        return document

    async def delete_form_import_job(self, form_id: str, provider: FormProvider):
        """
        Delete a Form Scheduler Configuration for a given form id and provider.

        Args:
            form_id (str): Form ID
            provider (FormProvider): Provider of the form

        Returns:
            dict: Document deleted
        """
        return await self.fsc_repo.delete(form_id, provider)
