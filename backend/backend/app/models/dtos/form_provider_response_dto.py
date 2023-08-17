from fastapi_camelcase import CamelModel


class FormProviderResponseDto(CamelModel):
    provider_name: str
