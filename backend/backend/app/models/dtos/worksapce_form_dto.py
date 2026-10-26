from typing import List

from common.ids import RecordId
from pydantic import BaseModel


class GroupsDto(BaseModel):
    group_ids: List[RecordId]
