from typing import Optional

from models.standard_form import StandardFormSettingDto
from schemas.google_form import GoogleFormDocument
from schemas.google_form_response import GoogleFormResponseDocument


class GoogleFormTransformerDto(GoogleFormDocument):
    """
    Data transfer object for transforming a Google Form stored in the database into a standard form.
    """

    settings: Optional[StandardFormSettingDto]


class GoogleFormResponseTransformDto(GoogleFormResponseDocument):
    """
    Data transfer object for transforming a Google Form response stored in the database into a standard form response.
    """

    formTitle: str
    formCustomUrl: Optional[str]
