from typing import Dict, List, Optional

from beanie import PydanticObjectId
from pydantic import BaseModel


class ResponderGroupDto(BaseModel):
    id: str = None
    name: str
    description: Optional[str] = None
    emails: List[str]

    def __init__(self, _id: PydanticObjectId, id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id = str(_id) if _id else id
