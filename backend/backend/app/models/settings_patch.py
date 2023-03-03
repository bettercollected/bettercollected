from typing import Optional

from pydantic import BaseModel


class SettingsPatchDto(BaseModel):
    pinned: Optional[bool]
    customUrl: Optional[str]
    private: Optional[bool]
    responseDataOwnerField: Optional[str]
