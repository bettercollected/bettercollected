from http import HTTPStatus
from beanie import PydanticObjectId
from fastapi import File, UploadFile

from backend.app.exceptions.http import HTTPException
from backend.app.models.dtos.media_libraries_dto import MediaType
from backend.app.repositories.media_library_repository import MediaLibraryRepository
from backend.app.services.aws_service import AWSS3Service
from starlette.requests import Request


class MediaLibraryService:
    MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024

    def __init__(
        self, media_library_repo: MediaLibraryRepository, aws_service: AWSS3Service
    ):
        self._media_library_repo = media_library_repo
        self._aws_service = aws_service

    async def get_medias_in_workspace_by_workspace_id(
        self, workspace_id: str, media_query: str
    ):
        return await self._media_library_repo.get_media_library_by_worksapce_id(
            workspace_id, media_query
        )

    async def delete_media_from_library_of_workspace(
        self, workspace_id: str, media_id: PydanticObjectId
    ):
        media = await self._media_library_repo.get_single_media_from_workspace_library(
            workspace_id=workspace_id, media_id=media_id
        )
        if media:
            await self._media_library_repo.delete_media_from_library(
                workspace_id, media_id
            )
            key = "media_library" + media.media_url.split("/media_library")[1]
            self._aws_service.delete_file_from_s3(key=key)
            return media_id
        else:
            raise HTTPException(status_code=404, content="Media not found")

    async def add_media_in_workspace_library(
        self,
        workspace_id: str,
        file: UploadFile,
        media_name: str,
        request: Request,
    ):
        if file is not None:
            file_type = check_if_file_is_of_supported_type(file)
            if not file_type:
                raise HTTPException(
                    status_code=415,
                    content="Unsupported file type.Only supporting images.",
                )
            file_size = get_file_size(request)
            if file_size > self.MAX_FILE_SIZE_BYTES:
                return HTTPException(
                    status_code=HTTPStatus.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content=HTTPStatus.REQUEST_HEADER_FIELDS_TOO_LARGE,
                )
            file_id = PydanticObjectId()
            s3_key = str(workspace_id) + str(file_id)
            media_url = await self._aws_service.upload_file_to_s3(
                file=file.file, key=s3_key, folder_name="media_library"
            )
            return await self._media_library_repo.add_media_in_workspace_library(
                media_type=(
                    MediaType.IMAGE if "image" in file.content_type else MediaType.VIDEO
                ),
                workspace_id=workspace_id,
                media_url=media_url,
                media_name=media_name,
                s3_key=s3_key,
            )
        else:
            raise HTTPException(
                status_code=400, content="No file found to upload in media"
            )


def get_file_size(request: Request):
    return int(request.headers["content-length"])


def check_if_file_is_of_supported_type(file: UploadFile):
    return "image" in file.content_type
