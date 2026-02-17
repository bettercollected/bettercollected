from fastapi_camelcase import CamelModel

from backend.app.models.dtos.minified_form import FormDtoCamelModel
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel


class SingleSubmissionResponse(CamelModel):
    form: FormDtoCamelModel
    response: StandardFormResponseCamelModel
