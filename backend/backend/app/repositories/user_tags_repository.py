from typing import List

from beanie import PydanticObjectId

from backend.app.models.dtos.user_tags_dto import UserTagsDto
from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.schemas.user_tags import UserTagsDocument
from common.base.repo import BaseRepository, U, T
from common.enums.form_provider import FormProvider
from common.db.routing import write_op


class UserTagsRepository(BaseRepository):
    async def get(self, item_id: str, provider: FormProvider) -> T:
        pass

    async def add(self, item: U | T) -> T:
        pass

    async def update(self, item_id: str, item: U | T) -> T:
        pass

    async def delete(self, item_id: str, provider: FormProvider):
        pass

    async def get_tags_by_id(self, user_id: str):
        return await UserTagsDocument.find_one({"user_id": PydanticObjectId(user_id)})

    async def list(self, **kwargs) -> List[UserTagsDocument]:
        return await UserTagsDocument.find().to_list()

    @write_op(replay=True)
    async def insert_user_tag(self, user_id: str, tag: UserTagType) -> UserTagsDocument:
        user_id = PydanticObjectId(user_id)
        await UserTagsDocument.find_one(UserTagsDocument.user_id == user_id).upsert(
            {"$addToSet": {UserTagsDocument.tags: tag}},
            on_insert=UserTagsDocument(user_id=user_id, tags=[tag]),
        )
        return await UserTagsDocument.find_one(UserTagsDocument.user_id == user_id)
