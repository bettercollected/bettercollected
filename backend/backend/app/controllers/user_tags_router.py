from typing import List

from classy_fastapi import Routable, get

from backend.app.container import container
from backend.app.models.user_tags import UserTags
from backend.app.router import router
from backend.app.services.user_tags_service import UserTagsService


@router(prefix="/user", tags=["User Tags"])
class UserTagsRoutes(Routable):

    def __init__(self, user_tags_service=container.user_tags_service(), *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_tags_service: UserTagsService = user_tags_service

    @get("/tags", response_model=List[UserTags])
    async def get_user_tags(self):
        return await self.user_tags_service.get_user_tags()
