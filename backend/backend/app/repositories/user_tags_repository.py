from typing import List

from beanie import PydanticObjectId

from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.models.user_tags import UserTags
from backend.app.schemas.user_tags import UserTagsDocument
from common.base.repo import BaseRepository, U, T
from common.enums.form_provider import FormProvider


class UserTagsRepository(BaseRepository):
    async def get(self, item_id: str, provider: FormProvider) -> T:
        pass

    async def add(self, item: U | T) -> T:
        pass

    async def update(self, item_id: str, item: U | T) -> T:
        pass

    async def delete(self, item_id: str, provider: FormProvider):
        pass

    async def list(self, **kwargs) -> List[UserTags]:
        return await UserTagsDocument.find().to_list()

    async def insert_user_tag(self, user_id: str, tag: UserTagType):
        user_id = PydanticObjectId(user_id)
        await UserTagsDocument.find_one(UserTagsDocument.user_id == user_id).upsert(
            {"$addToSet": {UserTagsDocument.tags: tag}},
            on_insert=UserTagsDocument(user_id=user_id, tags=[tag]))
