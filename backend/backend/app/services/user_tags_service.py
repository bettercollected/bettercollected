import requests

from backend.app.models.dtos.user_info_dto import UserInfoDto
from backend.app.models.dtos.user_tags_dto import UserTagsDetailsDto
from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.repositories.user_tags_repository import UserTagsRepository
from backend.config import settings


def _make_request(url: str, params=None):
    headers = {"accept": "application/json"}
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None


class UserTagsService:
    def __init__(self, user_tags_repo):
        self.user_tags_repo: UserTagsRepository = user_tags_repo

    async def get_user_tags(self):
        return await self.user_tags_repo.list()

    async def add_user_tag(self, user_id: str, tag: UserTagType):
        await self.user_tags_repo.insert_user_tag(user_id=user_id, tag=tag)

    async def get_user_tags_details(self):
        user_tags_list = await self.get_user_tags()
        user_ids = [item.user_id for item in user_tags_list]
        auth_users_url = f"{settings.auth_settings.BASE_URL}/users"
        query_params = {"user_ids": user_ids}
        response_data = _make_request(auth_users_url, params=query_params)
        user_info_list = [
            UserInfoDto(**user_info) for user_info in response_data["users_info"]
        ]
        zipped_users = [
            (user_tag, user_info)
            for user_tag, user_info in zip(user_tags_list, user_info_list)
            if user_tag.user_id == user_info.id
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
