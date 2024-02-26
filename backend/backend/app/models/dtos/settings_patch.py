import datetime
from typing import Optional

from fastapi_camelcase import CamelModel


class SettingsPatchDto(CamelModel):
    pinned: Optional[bool]
    custom_url: Optional[str]
    private: Optional[bool]
    response_data_owner_field: Optional[str]
    disable_branding: Optional[bool]
    hidden: Optional[bool] = False
    form_close_date: Optional[datetime.datetime | str]
    require_verified_identity: Optional[bool]
    show_submission_number: Optional[bool]
    allow_editing_response: Optional[bool]
