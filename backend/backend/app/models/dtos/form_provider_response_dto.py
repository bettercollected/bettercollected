from typing import Optional

from fastapi_camelcase import CamelModel
from pydantic import model_serializer


class FormProviderResponseDto(CamelModel):
    provider_name: str
    # Google Forms only: "on" or "readonly" (GOOGLE_FORMS_IMPORT; an "off"
    # provider is not listed). Imports are offered only when "on".
    import_mode: Optional[str] = None
    # Open Formulieren only: "on" when OPEN_FORMULIEREN_EXPORT is on (the
    # entry holds only the modes that are on; other providers never have it)
    export_mode: Optional[str] = None

    @model_serializer(mode="wrap")
    def _leave_out_an_unset_export_mode(self, handler):
        data = handler(self)
        if self.export_mode is None:
            data.pop("exportMode", None)
            data.pop("export_mode", None)
        return data
