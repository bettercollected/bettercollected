from typing import List

from common.records import RecordId
from pydantic import BaseModel

from backend.app.models.enum.user_tag_enum import UserTagType


class UserTags(BaseModel):
    user_id: RecordId
    tags: List[UserTagType]
