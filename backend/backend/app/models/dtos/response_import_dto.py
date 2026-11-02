"""Request bodies of the CSV import of responses."""

from typing import Dict

from fastapi_camelcase import CamelModel
from pydantic import Field, field_validator

from backend.app.services.response_import import limits


class ResponseImportRequest(CamelModel):
    """The mapping of a check or a run: the file's column positions (as text)
    to the target keys of the form (``GET .../imports/{id}`` lists them)."""

    mapping: Dict[str, str] = Field(default_factory=dict)
    # import only the valid rows instead of none at all when a row fails
    skip_invalid_rows: bool = False
    # a run only: the importer says they may store this data
    confirmed_lawful_basis: bool = False

    @field_validator("mapping")
    @classmethod
    def _bounded(cls, value: Dict[str, str]) -> Dict[str, str]:
        if len(value) > limits.MAX_COLUMNS:
            raise ValueError("too many columns")
        if any(len(str(k)) > 6 or len(str(v)) > 300 for k, v in value.items()):
            raise ValueError("a mapping entry is too long")
        return value
