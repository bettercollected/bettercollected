"""Application implementation - ready response."""

from typing import Any, Dict

from pydantic import BaseModel, ConfigDict


class ReadyResponse(BaseModel):
    """Define ready response model.

    Attributes:
        status (str): Strings are accepted as-is, int float and Decimal are
            coerced using str(v), bytes and bytearray are converted using
            v.decode(), enums inheriting from str are converted using
            v.value, and all other types cause an error.

    Raises:
        pydantic.ValidationError: If any of provided attribute
            doesn't pass type validation.

    """

    status: str

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Ready response model.",
        }
    )
