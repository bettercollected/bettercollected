from beanie import PydanticObjectId
from backend.app.exceptions.http import HTTPException
from backend.app.schemas.media_library import MediaLibraryDocument


class MediaLibraryRepository:

    async def get_media_library_by_worksapce_id(
        self, workspace_id: str, media_query: str
    ):
        if media_query is not None:
            return await MediaLibraryDocument.find(
                {
                    "workspace_id": workspace_id,
                    "media_name": {"$regex": media_query, "$options": "i"},
                }
            ).to_list()
        else:
            return await MediaLibraryDocument.find(
                {"workspace_id": workspace_id}
            ).to_list()

    async def get_single_media_from_workspace_library(
        self, workspace_id: str, media_id: PydanticObjectId
    ):
        return await MediaLibraryDocument.find_one(
            {"workspace_id": workspace_id, "media_id": media_id}
        )

    async def add_media_in_workspace_library(
        self,
        workspace_id: str,
        media_url: str,
        media_type: str,
        media_name: str,
        s3_key: str,
    ):
        media = MediaLibraryDocument(
            media_id=PydanticObjectId(),
            workspace_id=workspace_id,
            media_type=media_type,
            media_name=media_name,
            media_url=media_url,
            s3_key=s3_key,
        )
        await media.save()
        return media

    async def delete_media_from_library(
        self, workspace_id: str, media_id: PydanticObjectId
    ):
        media = await MediaLibraryDocument.find_one(
            {"workspace_id": workspace_id, "media_id": media_id}
        )
        await media.delete()
        return media_id
