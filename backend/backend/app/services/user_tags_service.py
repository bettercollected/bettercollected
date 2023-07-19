from beanie import PydanticObjectId

from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.repositories.user_tags_repository import UserTagsRepository


class UserTagsService:
    def __init__(self, user_tags_repo):
        self.user_tags_repo: UserTagsRepository = user_tags_repo

    async def get_user_tags(self):
        return await self.user_tags_repo.list()

    async def add_user_tag(self, user_id: str, tag: UserTagType):
        await self.user_tags_repo.insert_user_tag(user_id=user_id, tag=tag)
