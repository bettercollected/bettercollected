from backend.app.models.dtos.user_info_dto import UserInfoDto
from backend.app.models.dtos.user_tags_dto import UserTagsDetailsDto
from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.repositories.user_tags_repository import UserTagsRepository
from backend.app.utils import AiohttpClient
from backend.config import settings


class UserTagsService:
    def __init__(self, user_tags_repo):
        self.user_tags_repo: UserTagsRepository = user_tags_repo

    async def get_user_tags(self):
        return await self.user_tags_repo.list()

    async def add_user_tag(self, user_id: str, tag: UserTagType):
        await self.user_tags_repo.insert_user_tag(user_id=user_id, tag=tag)

    async def get_user_tags_details(self):
        user_tags_list = await self.get_user_tags()
        user_tags_list.sort(key=lambda user_tags: user_tags.user_id)
        user_ids = [str(item.user_id) for item in user_tags_list]
        query_params = {"user_ids": user_ids}
        response = await AiohttpClient.get_aiohttp_client().get(
            f"{settings.auth_settings.BASE_URL}/users", params=query_params
        )

        json_response = await response.json()
        user_info_list = [
            UserInfoDto(**user_info) for user_info in json_response["users_info"]
        ]
        user_info_list.sort(key=lambda user_info: user_info.id)
        zipped_users = [
            (user_tag, user_info)
            for user_tag, user_info in zip(user_tags_list, user_info_list)
        ]
        user_details_lists = [
            UserTagsDetailsDto(
                user_id=user[0].user_id,
                tags=user[0].tags,
                name=f"{user[1].first_name} {user[1].last_name}",
                email=user[1].email,
            )
            for user in zipped_users
        ]
        return user_details_lists
