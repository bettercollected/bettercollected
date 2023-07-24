from typing import List

from classy_fastapi import Routable, get

from backend.app.container import container
from backend.app.models.dtos.user_tags_dto import UserTagsDto, UserTagsDetailsDto
from backend.app.router import router
from backend.app.services.user_tags_service import UserTagsService


@router(prefix="/user/tags", tags=["User Tags"])
class UserTagsRoutes(Routable):
    def __init__(
        self, user_tags_service=container.user_tags_service(), *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.user_tags_service: UserTagsService = user_tags_service

    @get("/", response_model=List[UserTagsDto])
    async def get_user_tags(self):
        return await self.user_tags_service.get_user_tags()

    @get("/details", response_model=List[UserTagsDetailsDto])
    async def get_user_tags_details(self):
        return await self.user_tags_service.get_user_tags_details()
