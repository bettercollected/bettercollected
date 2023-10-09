from typing import List

from beanie import PydanticObjectId
from pydantic import BaseModel


class GroupsDto(BaseModel):
    group_ids: List[PydanticObjectId]


