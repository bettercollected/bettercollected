import re
from typing import List

from pydantic import BaseModel, validator

from models.form_provider import FormProvider


class FormSchedulerConfigQuery(BaseModel):
    email: List[str]
    provider: FormProvider
    formId: str


class AddNewFormImportJobRequest(FormSchedulerConfigQuery):
    # noinspection PyNestedDecorators
    @validator("email")
    @classmethod
    def must_be_valid_email(cls, v: List[str]):
        regex = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        email = []
        for value in v:
            if not re.search(regex, value):
                raise ValueError("Must be a valid email address.")
            email.append(value.lower())
        return email
