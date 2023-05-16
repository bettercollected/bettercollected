from typing import Dict, List

from beanie import PydanticObjectId
from pydantic import BaseModel


class ResponderGroupDto(BaseModel):
    id: str = None
    name: str
    emails: List[Dict[str, str]]

    def __init__(self, _id: PydanticObjectId, id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id = str(_id) if _id else id
