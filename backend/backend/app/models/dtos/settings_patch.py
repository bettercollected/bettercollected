import datetime
from typing import Optional

from pydantic import BaseModel


class SettingsPatchDto(BaseModel):
    pinned: Optional[bool]
    customUrl: Optional[str]
    private: Optional[bool]
    responseDataOwnerField: Optional[str]
    disableBranding: Optional[bool]
    hidden: Optional[bool] = False
    formCloseDate: Optional[datetime.datetime | str]
