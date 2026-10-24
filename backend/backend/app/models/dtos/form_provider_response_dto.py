from typing import Optional

from fastapi_camelcase import CamelModel


class FormProviderResponseDto(CamelModel):
    provider_name: str
    # Google Forms only: "on" or "readonly" (GOOGLE_FORMS_IMPORT; an "off"
    # provider is not listed). Imports are offered only when "on".
    import_mode: Optional[str] = None
