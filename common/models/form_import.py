from typing import Dict, Any, Optional, List

from pydantic import BaseModel

from common.models.standard_form import StandardFormDto, StandardFormResponseDto


class FormImportRequestBody(BaseModel):
    form: Dict[str, Any]
    response_data_owner: Optional[str]


class FormImportResponse(BaseModel):
    form: StandardFormDto
    responses: List[StandardFormResponseDto]
