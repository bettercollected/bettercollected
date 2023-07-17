from backend.app.repositories.user_tags_repository import UserTagsRepository
from common.utils.asyncio_run import asyncio_run


class UserTagsService:
    def __init__(self, user_tags_repo):
        self.user_tags_repo: UserTagsRepository = user_tags_repo

    async def get_user_tags(self):
        return await self.user_tags_repo.list()
