from typing import List

from beanie import PydanticObjectId
from pydantic import BaseModel

from backend.app.models.enum.user_tag_enum import UserTagType


class UserTags(BaseModel):
    user_id: PydanticObjectId
    tags: List[UserTagType]
