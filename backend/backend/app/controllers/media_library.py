from typing import List
from beanie import PydanticObjectId
from classy_fastapi import Routable, delete, get, post
from fastapi import Depends, UploadFile
from common.models.user import User

from backend.app.container import container
from backend.app.models.dtos.media_libraries_dto import (
    MediaLibraryCamelModel,
    MediaLibraryDto,
    MediaType,
)
from backend.app.router import router
from backend.app.services.media_library_service import MediaLibraryService
from backend.app.services.user_service import get_logged_user
from starlette.requests import Request


@router(prefix="/workspaces/{workspace_id}/media", tags=["Media Library"])
class MediaLibrary(Routable):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.media_library_service: MediaLibraryService = (
            container.media_library_service()
        )

    @get("", response_model=List[MediaLibraryCamelModel])
    async def get_workspace_media(
        self,
        workspace_id: str,
        media_query: str = None,
        user: User = Depends(get_logged_user),
    ):
        return await self.media_library_service.get_medias_in_workspace_by_workspace_id(
            workspace_id, media_query
        )

    @post("", response_model=MediaLibraryCamelModel)
    async def post_media_in_workspace(
        self,
        workspace_id: str,
        request: Request,
        file: UploadFile = None,
        user: User = Depends(get_logged_user),
    ):
        media = await self.media_library_service.add_media_in_workspace_library(
            workspace_id=workspace_id,
            file=file,
            media_name=file.filename,
            request=request,
        )
        return MediaLibraryDto(**media.dict())

    @delete("/{media_id}")
    async def delete_media_from_workspace(
        self,
        workspace_id: str,
        media_id: PydanticObjectId,
        user: User = Depends(get_logged_user),
    ):
        return await self.media_library_service.delete_media_from_library_of_workspace(
            workspace_id=workspace_id, media_id=media_id
        )
