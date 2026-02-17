"""Application implementation - error response."""

from http import HTTPStatus
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, model_validator, ConfigDict


class ErrorModel(BaseModel):
    """Define base error model for the response.

    Attributes:
        code (int): HTTP error status code.
        message (str): Detail on HTTP error.
        status (str): HTTP error reason-phrase as per in RFC7235. NOTE! Set
            automatically based on HTTP error status code.

    Raises:
        pydantic.ValidationError: If any of provided attribute
            doesn't pass type validation.

    """

    code: int
    message: str
    details: Optional[List[Dict[str, Any]]] = None
    status: Optional[str] = None

    @model_validator(mode="after")
    def _set_status(self) -> "ErrorModel":
        """Set the status field value based on the code attribute value.

        Returns:
            ErrorModel: The ErrorModel object with the status field.

        """
        self.status = HTTPStatus(self.code).name
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Error model.",
            "properties": {
                "status": {"title": "Status", "type": "string"},
            },
            "required": ["status"],
        }
    )


class ErrorResponse(BaseModel):
    """Define error response model.

    Attributes:
        error (ErrorModel): ErrorModel class object instance.

    Raises:
        pydantic.error_wrappers.ValidationError: If any of provided attribute
            doesn't pass type validation.

    """

    error: ErrorModel

    def __init__(self, **kwargs):
        """Initialize ErrorResponse class object instance."""
        # Neat trick to still use kwargs on ErrorResponse model.
        super().__init__(error=ErrorModel(**kwargs))

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Error response model.",
        }
    )
