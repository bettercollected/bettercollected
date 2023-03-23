from typing import Any, Dict, List, Optional

from common.models.standard_form import StandardForm, StandardFormResponse

from pydantic import BaseModel


class FormImportRequestBody(BaseModel):
    form: Dict[str, Any]
    response_data_owner: Optional[str]


class FormImportResponse(BaseModel):
    form: StandardForm
    responses: List[StandardFormResponse]
