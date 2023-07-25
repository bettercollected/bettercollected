from typing import List

from classy_fastapi import Routable, get
from fastapi import Depends

from backend.app.container import container
from backend.app.exceptions.forbidden_exception import ForbiddenException
from backend.app.models.dtos.user_tags_dto import UserTagsDto, UserTagsDetailsDto
from backend.app.router import router
from backend.app.services.user_service import get_logged_user
from backend.app.services.user_tags_service import UserTagsService
from common.models.user import User


@router(prefix="/user/tags", tags=["User Tags"])
class UserTagsRoutes(Routable):
    def __init__(
        self, user_tags_service=container.user_tags_service(), *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.user_tags_service: UserTagsService = user_tags_service

    @get("/", response_model=List[UserTagsDto])
    async def get_user_tags(
        self,
        user: User = Depends(get_logged_user),
    ):
        if not user.is_admin():
            raise ForbiddenException()
        return await self.user_tags_service.get_user_tags()

    @get("/details", response_model=List[UserTagsDetailsDto])
    async def get_user_tags_details(self, user: User = Depends(get_logged_user)):
        if not user.is_admin():
            raise ForbiddenException()
        return await self.user_tags_service.get_user_tags_details()
