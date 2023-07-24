from typing import List

from beanie import PydanticObjectId
from fastapi_camelcase import CamelModel

from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.models.user_tags import UserTags


class UserTagsDto(CamelModel, UserTags):
    """Model for updating user tags"""

    user_id: PydanticObjectId
    tags: List[UserTagType]


class UserTagsDetailsDto(UserTagsDto):
    name: str
    email: str
