from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from common.models.standard_form import StandardForm, StandardFormResponse


class FormImportRequestBody(BaseModel):
    form: Dict[str, Any]
    response_data_owner: Optional[str] = None


class FormImportResponse(BaseModel):
    form: Optional[StandardForm] = None
    responses: Optional[List[StandardFormResponse]] = None
