from fastapi_camelcase import CamelModel

from backend.app.schemas.consent import Consent
from common.models.consent import ConsentResponse


class ConsentCamelModel(Consent, CamelModel):
    pass


class ConsentResponseCamelModel(ConsentResponse, CamelModel):
    pass
