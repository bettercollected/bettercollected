from fastapi_camelcase import CamelModel

from backend.app.schemas.consent import Consent


class ConsentCamelModel(Consent, CamelModel):
    pass
