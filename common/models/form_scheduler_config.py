import re
from typing import List

from pydantic import BaseModel, validator

from enums.form_provider import FormProvider


class FormSchedulerConfigQuery(BaseModel):
    """
    Model for querying form scheduler configurations.
    """

    email: List[str]
    provider: FormProvider
    formId: str


class AddNewFormImportJobRequest(FormSchedulerConfigQuery):
    """
    Model for requests to add new form import jobs.
    Extends the `FormSchedulerConfigQuery` model.
    """

    # noinspection PyNestedDecorators
    @validator("email")
    @classmethod
    def must_be_valid_email(cls, v: List[str]):
        """
        Validates that the given list of emails are all valid.

        Args:
            v: The list of emails to validate.
        Returns:
            The list of emails in lowercase.
        Raises:
            ValueError: If any email is not valid.
        """
        regex = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        email = []
        for value in v:
            if not re.search(regex, value):
                raise ValueError("Must be a valid email address.")
            email.append(value.lower())
        return email
