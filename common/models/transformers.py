from typing import Optional

from models.standard_form import StandardFormSettingDto
from schemas.google_form import GoogleFormDocument
from schemas.google_form_response import GoogleFormResponseDocument


class GoogleFormTransformerDto(GoogleFormDocument):
    settings: Optional[StandardFormSettingDto]


class GoogleFormResponseTransformDto(GoogleFormResponseDocument):
    formTitle: str
    formCustomUrl: Optional[str]
