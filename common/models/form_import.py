from typing import Dict, Any, Optional, List

from pydantic import BaseModel

from common.models.standard_form import StandardForm, StandardFormResponse


class FormImportRequestBody(BaseModel):
    form: Dict[str, Any]
    response_data_owner: Optional[str]


class FormImportResponse(BaseModel):
    form: StandardForm
    responses: List[StandardFormResponse]
