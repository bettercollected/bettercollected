from typing import Optional

from fastapi_camelcase import CamelModel

from common.models.standard_form import StandardForm, StandardFormResponse, StandardFormSettings


class StandardFormSettingsCamelModel(StandardFormSettings, CamelModel):
    pass


class StandardFormCamelModel(StandardForm, CamelModel):
    settings: Optional[StandardFormSettingsCamelModel]


class StandardFormResponseCamelModel(StandardFormResponse, CamelModel):
    form_title: Optional[str]
