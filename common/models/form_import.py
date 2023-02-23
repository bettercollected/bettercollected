from typing import Dict, Any, Optional

from pydantic import BaseModel


class FormImportRequestBody(BaseModel):
    form: Dict[str, Any]
    response_data_owner: Optional[str]
